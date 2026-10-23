.PHONY: verify test playground

verify: playground edge-tests
	@echo "VERIFY OK"

edge-tests:
	cd edge && node test_diamond_edge.mjs && node test_diamond_storage.mjs && node test_diamond_architecture.mjs && node test_reality_standard.mjs

playground:
	cd playground && python3 test_frontier.py -q && python3 test_purity_phase2.py -q && python3 test_purity_phase3.py -q && python3 test_infinite_edges.py -q && python3 test_diamond_edge.py -q && python3 test_omni.py -q && python3 test_gui_wiring.py -q && python3 test_purity_logic.py -q && python3 test_standing_boundary.py -q

test: playground

broad-tests:
	@echo "--- dclm ---"
	-cd dclm && python3 -m unittest discover -s . -p "test_*.py" -q
	@echo "--- economics ---"
	-cd economics && python3 -m unittest discover -s . -p "test_*.py" -q
	@echo "--- iris-intake ---"
	-cd iris-intake && python3 -m unittest discover -s . -p "test_*.py" -q

verify-all: verify broad-tests
	@echo "VERIFY-ALL DONE (broad suites best-effort)"

omni: edge-tests
	cd edge && node omni_idempotent.mjs
