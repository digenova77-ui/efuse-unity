.PHONY: verify test playground

verify: playground
	@echo "VERIFY OK"

playground:
	cd playground && python3 test_frontier.py -q && python3 test_purity_phase2.py -q

test: playground
