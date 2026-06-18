'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:28:00
@Description：Pydantic 模型契约测试（FunctionNode / CallEdge / TagEvidence /
              CalculationReport / PipelineRunResult / RunSummary）。
'''


from datetime import datetime

from pyknp.model.edge import CallEdge, ResolvedVia
from pyknp.model.function import FunctionNode
from pyknp.model.graph_payload import GraphEdge, GraphNode, GraphPayload
from pyknp.model.run import CalculationReport, PipelineRunResult, RunStatus, RunSummary
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence


def test_function_node_with_location_id_optional():
    fn = FunctionNode(
        ref_id="pkg.mod.foo",
        qualified_name_in_file="foo",
        file="pkg/mod.py",
        start_line=10,
        end_line=20,
        parameters=["x", "y"],
        decorators=[],
        source_hash="abc123",
    )
    assert fn.location_id is None


def test_function_node_with_location_id_filled():
    fn = FunctionNode(
        ref_id="pkg.mod.foo",
        qualified_name_in_file="foo",
        file="pkg/mod.py",
        start_line=10,
        end_line=20,
        parameters=[],
        decorators=[],
        source_hash="abc123",
        location_id="pkg/mod.py:10",
    )
    assert fn.location_id == "pkg/mod.py:10"


def test_call_edge_unresolved_callee():
    edge = CallEdge(
        caller_location_id="pkg/mod.py:10",
        callee_location_id=None,
        callee_ref_id_attempt="some_func",
        call_line=15,
        resolved_via=ResolvedVia.UNRESOLVED,
    )
    assert edge.callee_location_id is None


def test_tag_evidence_serialization():
    ev = TagEvidence(
        tag=Tag.NETWORK,
        function_id="pkg/mod.py:10",
        rule_id="network.requests_get",
        evidence="import requests\n  line 15: requests.get(...)",
    )
    assert ev.rule_id == "network.requests_get"


def test_calculation_report_defaults_via_model():
    report = CalculationReport(
        total_functions=0,
        total_edges=0,
        tag_distribution={},
        tag_distribution_pct={},
        in_degree_top10=[],
        out_degree_top10=[],
        pagerank_top10=[],
        betweenness_top10=[],
        module_tag_distribution={},
    )
    assert report.total_functions == 0


def test_pipeline_run_result_status_enum():
    assert RunStatus.SUCCESS == "success"
    assert RunStatus.FAILED == "failed"
    assert RunStatus.RUNNING == "running"


def test_pipeline_run_result_round_trip():
    fn = FunctionNode(
        ref_id="pkg.mod.foo",
        qualified_name_in_file="foo",
        file="pkg/mod.py",
        start_line=10,
        end_line=20,
        parameters=[],
        decorators=[],
        source_hash="abc",
        location_id="pkg/mod.py:10",
    )
    started = datetime(2026, 6, 15, 12, 0, 0)
    finished = datetime(2026, 6, 15, 12, 0, 5)
    result = PipelineRunResult(
        run_id="r1",
        status=RunStatus.SUCCESS,
        started_at=started,
        finished_at=finished,
        project_name="demo",
        functions=[fn],
        edges=[],
        direct_tags={},
        propagated_tags={},
        calculation=CalculationReport(
            total_functions=1,
            total_edges=0,
            tag_distribution={},
            tag_distribution_pct={},
            in_degree_top10=[],
            out_degree_top10=[],
            pagerank_top10=[],
            betweenness_top10=[],
            module_tag_distribution={},
        ),
        errors=[],
    )
    assert result.run_id == "r1"
    assert result.functions[0].ref_id == "pkg.mod.foo"


def test_run_summary_minimal():
    summary = RunSummary(
        run_id="r1",
        project_name="demo",
        status=RunStatus.SUCCESS,
        started_at=datetime(2026, 6, 15, 12, 0, 0),
        total_functions=10,
        total_edges=20,
    )
    assert summary.run_id == "r1"


def test_graph_node_minimal():
    node = GraphNode(
        location_id="pkg/mod.py:10",
        ref_id="pkg.mod.foo",
        label="foo",
        file="pkg/mod.py",
        tags=[Tag.NETWORK],
        in_degree=2,
        out_degree=1,
        pagerank=0.05,
    )
    assert node.label == "foo"


def test_graph_payload_serialization_roundtrip():
    payload = GraphPayload(
        run_id="r1",
        nodes=[
            GraphNode(
                location_id="a:1", ref_id="a.f", label="f", file="a",
                tags=[], in_degree=0, out_degree=1, pagerank=0.0,
            ),
        ],
        edges=[
            GraphEdge(source="a:1", target="b:2", resolved_via=ResolvedVia.JEDI_GOTO),
        ],
        tag_distribution={},
    )
    js = payload.model_dump_json()
    restored = GraphPayload.model_validate_json(js)
    assert restored.nodes[0].location_id == "a:1"
