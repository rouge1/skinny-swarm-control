Review feedback on your gates (swarm_control/sim/gates.py). It passed on correctness; fix these. Edit only that file.

1. [medium] apply_gates does np.repeat(crossing, per_parent) before capping to the pool's free slots: an add-10000
   gate with 10 free slots allocates 319 MB and takes 47 ms. Cap first: only repeat the parents that fit
   (crossing[:ceil(free / per_parent)]), then trim to `free`.
2. [low] Huge values (value=10**30) raise a raw OverflowError; clamp copies per parent to the free slots so no
   huge arrays are ever built.
3. [low] move_gates with absurd speed (vx=1e9, dt=1) spins a 1M-iteration bounce loop and lands in the wrong place.
   Replace the loop with a closed form: fold the position with modulo 2*L (L = field_w - w) and reflect once.
4. [low] A gate wider than the field is clamped to x=0 only when it moves; clamp it the same way regardless of vx.
5. [low] A gate that starts outside the field jumps by up to 160 px in one tick; clamp x into [0, field_w - w]
   before integrating.
6. [low] Trim per-frame validation to cheap checks (it is ~16% of the call), and raise TypeError (not ValueError)
   for a wrong `passed` dtype or wrong argument types.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_gates.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
