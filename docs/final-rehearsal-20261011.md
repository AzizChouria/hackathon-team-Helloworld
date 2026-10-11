# Local final rehearsal (2026-10-11)

Merged organisers' kit update `273a9bc`, retaining our concurrent
`play_threads`. Started `arena-sim serve --final-rehearsal --data
../data/package` from `starter-kit`, registered a private simulator key, and
ran our `arena run --set final --waves 2 --agent buyer --data ../data
--parallel 10 -v` against localhost.

The runner received 403 before the final opened, then started wave 1 at
09:57:56 CEST and wave 2 at 10:02:21. All three cases in each wave closed
deals by 09:58:01 and 10:02:27 respectively, well before the 10:01:51 and
10:06:21 caps. It logged both wave closures and exited cleanly with status 0
after the second wave. There were six deals and no runner errors.

The merged kit passed **134 tests, 1 skipped** and Ruff before rehearsal.
This simulator checks final-wave mechanics; its scripted supplier does not
predict the hidden suppliers' scores.
