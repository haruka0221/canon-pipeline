#!/usr/bin/env python3
"""Mock SRU server for testing run_bl_calibration_v2_v1.py. Never contacts the BL.

    python scripts/bl/mock_sru_server_v1.py --port 8765 [--fail-after N] [--fail-code 429]

Behaviour:
  * numberOfRecords is derived from the query: 'creator' queries -> 250
    (above CAP, so A1 is skipped), queries containing 'DIAG' -> SRU
    diagnostic, otherwise a stable pseudo-random count in [0, 45]
  * pages of maximumRecords records with MARC 001 = <query hash>-<n>
  * after --fail-after successful responses, every request gets
    --fail-code (default 429) so the runner's stop rule can be tested
  * logs each request line to stdout
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import urllib.parse
import xml.sax.saxutils as sx

SRU_NS = "http://www.loc.gov/zing/srw/"
MARC_NS = "http://www.loc.gov/MARC21/slim"


def make_record(key, i):
    return (f'<record><recordSchema>marcxml</recordSchema><recordPacking>xml</recordPacking>'
            f'<recordData><record xmlns="{MARC_NS}"><leader>00000nam a2200000 a 4500</leader>'
            f'<controlfield tag="001">{key}-{i}</controlfield>'
            f'<controlfield tag="008">900101s1901    enk           000 1 eng  </controlfield>'
            f'<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Mock title {i}.</subfield>'
            f'</datafield></record></recordData><recordPosition>{i}</recordPosition></record>')


class Handler(http.server.BaseHTTPRequestHandler):
    ok_count = 0

    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        query = qs.get("query", [""])[0]
        start = int(qs.get("startRecord", ["1"])[0])
        page = int(qs.get("maximumRecords", ["20"])[0])
        cfg = self.server.cfg
        if cfg.fail_after is not None and Handler.ok_count >= cfg.fail_after:
            self.send_response(cfg.fail_code)
            self.end_headers()
            print(f"FAIL {cfg.fail_code} start={start} {query}")
            return
        key = hashlib.sha1(query.encode()).hexdigest()[:8]
        if "DIAG" in query:
            body = (f'<searchRetrieveResponse xmlns="{SRU_NS}"><version>1.2</version>'
                    f'<numberOfRecords>0</numberOfRecords><diagnostics>'
                    f'<diagnostic xmlns="http://www.loc.gov/zing/srw/diagnostic/">'
                    f'<uri>info:srw/diagnostic/1/10</uri><message>Query syntax error</message>'
                    f'</diagnostic></diagnostics></searchRetrieveResponse>')
        else:
            n = 250 if "creator" in query else int(key, 16) % 46
            recs = [make_record(key, i) for i in range(start, min(n, start + page - 1) + 1)]
            body = (f'<searchRetrieveResponse xmlns="{SRU_NS}"><version>1.2</version>'
                    f'<numberOfRecords>{n}</numberOfRecords><records>{"".join(recs)}</records>'
                    f'<echoedSearchRetrieveRequest><query>{sx.escape(query)}</query>'
                    f'</echoedSearchRetrieveRequest></searchRetrieveResponse>')
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        Handler.ok_count += 1
        print(f"OK #{Handler.ok_count} start={start} {query}")

    def log_message(self, *a):  # quiet default logging
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--fail-after", type=int, default=None)
    ap.add_argument("--fail-code", type=int, default=429)
    cfg = ap.parse_args()
    srv = http.server.HTTPServer(("127.0.0.1", cfg.port), Handler)
    srv.cfg = cfg
    print(f"mock SRU on http://127.0.0.1:{cfg.port}/sru  fail_after={cfg.fail_after} "
          f"code={cfg.fail_code}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
