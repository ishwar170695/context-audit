import argparse
import io
import sys
import pytest
from context_audit.cli import run_receipt_flow

def test_receipt_flow_latest_no_open(capsys):
    args = argparse.Namespace(
        agent=None,
        latest=True,
        no_open=True,
        input_price=3.00,
        cache_price=0.30
    )
    run_receipt_flow(args)
    captured = capsys.readouterr()
    assert "Scanning for installed coding agents" in captured.out
    assert "RECEIPT" in captured.out
    assert "YOU PAID:" in captured.out
    assert "FOR:               REPEATED CONTEXT" in captured.out
    assert "Total Session Bill:" in captured.out

def test_receipt_flow_specific_agent(capsys):
    args = argparse.Namespace(
        agent="cursor",
        latest=True,
        no_open=True,
        input_price=3.00,
        cache_price=0.30
    )
    run_receipt_flow(args)
    captured = capsys.readouterr()
    assert "CURSOR RECEIPT" in captured.out
    assert "YOU PAID:" in captured.out

def test_receipt_flow_interactive_selection(monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin', io.StringIO('1\n1\n'))
    args = argparse.Namespace(
        agent=None,
        latest=False,
        no_open=True,
        input_price=3.00,
        cache_price=0.30
    )
    run_receipt_flow(args)
    captured = capsys.readouterr()
    assert "RECEIPT" in captured.out
    assert "YOU PAID:" in captured.out
