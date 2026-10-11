# Final launch script check (2026-10-11)

`starter-kit/scripts/final_run.sh` passed `bash -n`. `systemd-inhibit
--what=sleep:idle true` succeeded on this machine. The script found the
Sunday-release facts, checked `arena me` against a local simulator key, and
ran `buyer` with `FINAL_RUN_WAVES=2` against a separate final-rehearsal
simulator on localhost. It logged both wave closures, six deals, and a clean
exit. The test log stayed local and is ignored by git.

A second local run injected one `uv run arena run` exit code 77. The script
recorded the failure, waited five seconds, relaunched the runner, and exited
normally after the rehearsal. That run began late in wave 2, so its scores
are not a performance check. The injected failure verifies the shell restart
path; the runner's session-resume behavior is implemented in `RemoteTable`.

No hosted practice sessions were used for these checks.
