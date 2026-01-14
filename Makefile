PYTHON ?= python3
PYTHONPATH := src
word ?= $(w)
WORD ?= $(word)

run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m word_agent $(WORD)

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests
