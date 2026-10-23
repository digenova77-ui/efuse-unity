.PHONY: verify test playground

verify: playground
	@echo "VERIFY OK"

playground:
	cd playground && python3 test_frontier.py -q && python3 test_purity_phase2.py -q && python3 test_purity_phase3.py -q && python3 test_infinite_edges.py -q && python3 test_diamond_edge.py -q && python3 test_omni.py -q

test: playground
