.PHONY: verify test playground

verify: playground edge-tests
	@echo "VERIFY OK"

edge-tests:
	cd edge && node test_diamond_edge.mjs

playground:
	cd playground && python3 test_frontier.py -q && python3 test_purity_phase2.py -q && python3 test_purity_phase3.py -q && python3 test_infinite_edges.py -q && python3 test_diamond_edge.py -q && python3 test_omni.py -q && python3 test_gui_wiring.py -q && python3 test_purity_logic.py -q && python3 test_standing_boundary.py -q

test: playground
