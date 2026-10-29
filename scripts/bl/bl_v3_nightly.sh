#!/usr/bin/env bash
# Nightly driver for the BL production v3 run. Run inside tmux on the server:
#   tmux new -s bl_v3
#   bash scripts/bl/bl_v3_nightly.sh <contact-email> [first-date YYYY-MM-DD]
#
# Each day at 07:05 JST (22:05 GMT, inside the London night window) it runs
# batches in order (1..34), skipping batches whose latest manifest says
# batch_complete=true, until the night's request count reaches NIGHT_CAP or the
# runner stops for the window / per-run cap. On ANY other stop (HTTP, network,
# diagnostic, parse) the loop ends and does not reschedule: a human reviews the
# log and restarts the script. Nothing here changes the runner's own guards.
set -u
CONTACT="${1:?contact e-mail required}"
FIRST_DATE="${2:-$(date +%F)}"
NIGHT_CAP=7000
START_HHMM="07:05"
REPO="$HOME/canon-pipeline-bl"
RET="$REPO/derived/bl_production/production_v3/retrieval"
RAW="/media/hdd1/user/tsutsui/bl/production_v3_raw"
LOG="$RET/nightly_driver.log"
cd "$REPO" || exit 1
source "$HOME/venvs/canon/bin/activate"
mkdir -p "$RET"

say() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }

batch_complete() {  # $1 = batch number
  python3 - "$1" <<'PY'
import glob, json, sys
b = int(sys.argv[1]); ms = sorted(glob.glob(f"derived/bl_production/production_v3/retrieval/batch_{b:03d}/run_manifest_*.json"))
print("yes" if ms and json.load(open(ms[-1])).get("batch_complete") else "no")
PY
}

last_stop_and_sent() {  # $1 = batch number -> "sent<TAB>stop_reason"
  python3 - "$1" <<'PY'
import glob, json, sys
b = int(sys.argv[1]); ms = sorted(glob.glob(f"derived/bl_production/production_v3/retrieval/batch_{b:03d}/run_manifest_*.json"))
m = json.load(open(ms[-1])) if ms else {}
print(f"{m.get('http_requests_this_invocation',0)}\t{m.get('stop_reason','')}")
PY
}

say "driver started; first night $FIRST_DATE $START_HHMM JST; night cap $NIGHT_CAP"
night_date="$FIRST_DATE"
while true; do
  target_epoch=$(date -d "$night_date $START_HHMM" +%s)
  now=$(date +%s)
  if (( target_epoch > now )); then
    say "sleeping until $night_date $START_HHMM JST ($(( (target_epoch-now)/60 )) min)"
    sleep $(( target_epoch - now ))
  fi
  git fetch -q origin bl-production-v3 && git merge -q --ff-only origin/bl-production-v3 || say "WARNING: fetch/ff failed, continuing with local HEAD $(git rev-parse --short HEAD)"
  spent=0; fatal=""
  for b in $(seq 1 34); do
    [[ "$(batch_complete "$b")" == "yes" ]] && continue
    remaining=$(( NIGHT_CAP - spent ))
    (( remaining <= 0 )) && { say "night cap reached ($spent)"; break; }
    say "batch $b: starting, remaining tonight $remaining"
    python scripts/bl/run_bl_production_v3_v1.py --batch "$b" --execute --contact "$CONTACT" \
      --raw-root "$RAW" --max-requests "$remaining" >> "$LOG" 2>&1
    IFS=$'\t' read -r sent reason < <(last_stop_and_sent "$b")
    spent=$(( spent + sent ))
    say "batch $b: sent $sent (tonight $spent); stop_reason='${reason}'"
    if [[ -z "$reason" ]]; then
      git add "$RET/batch_$(printf %03d "$b")/" && git commit -q -m "BL v3: batch $b retrieval log ($(date +%F))" && git push -q origin bl-production-v3 || say "WARNING: commit/push of batch $b failed"
      continue
    fi
    case "$reason" in
      *"per-run cap"*|*"outside night window"*|*"cumulative cap"*) break ;;
      *) fatal="$reason"; break ;;
    esac
  done
  git add "$RET/" 2>/dev/null && git commit -q -m "BL v3: partial retrieval log ($(date +%F))" 2>/dev/null && git push -q origin bl-production-v3 2>/dev/null
  if [[ -n "$fatal" ]]; then
    say "FATAL STOP: $fatal — driver ends; review the log, then restart the script"
    exit 3
  fi
  if [[ "$(batch_complete 34)" == "yes" ]]; then
    say "all batches complete; driver ends"; exit 0
  fi
  night_date=$(date -d "$night_date + 1 day" +%F)
  say "night done ($spent requests); next night $night_date"
done
