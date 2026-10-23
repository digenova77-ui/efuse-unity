.PHONY: verify test playground

verify: playground
	@echo "VERIFY OK"

playground:
	cd playground && python3 test_frontier.py -q

test: playground
