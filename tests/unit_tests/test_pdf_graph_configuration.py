from langgraph.pregel import Pregel

from agent.pdf_graph import graph


def test_pdf_graph_is_valid_pregel() -> None:
    assert isinstance(graph, Pregel)
