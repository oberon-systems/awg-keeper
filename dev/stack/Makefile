# The whole product on one machine: compose for the panel and one agent over a
# fake awg/xray host baked into its image. The stand keeps no state.

.PHONY: kickstart down restart logs calls

export LISTEN_PORT STATS_PORT

# stack
kickstart down restart logs calls:
	bash kickstart.sh $@
