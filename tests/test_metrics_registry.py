from __future__ import annotations

from packages.shared.metrics import MetricsRegistry, scrape_token_matches


def test_unlabelled_counter_and_gauge_render_like_before() -> None:
    registry = MetricsRegistry()
    registry.inc("ingestion_runs_total", 2, help_text="Runs.")
    registry.set("worker_failed_dispatch_ratio", 0.25, help_text="Ratio.")

    text = registry.render_prometheus_text()

    assert "# TYPE ingestion_runs_total counter\ningestion_runs_total 2\n" in text
    assert "worker_failed_dispatch_ratio 0.25\n" in text


def test_labelled_series_are_sorted_and_escaped() -> None:
    registry = MetricsRegistry()
    registry.inc("requests_total", 1, help_text="Requests.", labels={"route": "/b", "method": "GET"})
    registry.inc("requests_total", 2, help_text="Requests.", labels={"route": "/a", "method": "GET"})
    registry.set("odd", 1, help_text="Odd\nhelp.", labels={"value": 'quote"back\\slash'})

    text = registry.render_prometheus_text()

    assert 'requests_total{method="GET",route="/a"} 2\nrequests_total{method="GET",route="/b"} 1' in text
    assert 'odd{value="quote\\"back\\\\slash"} 1' in text
    assert "# HELP odd Odd\\nhelp." in text
    assert registry.value("requests_total", {"method": "GET", "route": "/a"}) == 2


def test_histogram_renders_cumulative_buckets_sum_and_count() -> None:
    registry = MetricsRegistry()
    for value in (0.05, 0.2, 3.0):
        registry.observe(
            "latency_seconds",
            value,
            help_text="Latency.",
            buckets=(0.1, 1.0),
            labels={"route": "/x"},
        )

    text = registry.render_prometheus_text()

    assert "# TYPE latency_seconds histogram" in text
    assert 'latency_seconds_bucket{route="/x",le="0.1"} 1' in text
    assert 'latency_seconds_bucket{route="/x",le="1.0"} 2' in text
    assert 'latency_seconds_bucket{route="/x",le="+Inf"} 3' in text
    assert 'latency_seconds_count{route="/x"} 3' in text
    assert 'latency_seconds_sum{route="/x"} 3.25' in text


def test_declared_histogram_renders_metadata_without_samples() -> None:
    registry = MetricsRegistry()
    registry.declare_histogram("refresh_seconds", help_text="Refresh.")

    text = registry.render_prometheus_text()

    assert "# TYPE refresh_seconds histogram" in text
    assert "refresh_seconds_bucket" not in text


def test_replace_series_drops_series_that_disappeared() -> None:
    registry = MetricsRegistry()
    registry.replace_series(
        "lag_seconds", [({"source": "a"}, 1.0), ({"source": "b"}, 2.0)], help_text="Lag."
    )
    registry.replace_series("lag_seconds", [({"source": "b"}, 5.0)], help_text="Lag.")

    text = registry.render_prometheus_text()

    assert 'lag_seconds{source="a"}' not in text
    assert 'lag_seconds{source="b"} 5' in text


def test_scrape_token_matching_uses_dedicated_scheme() -> None:
    assert scrape_token_matches(None, None) is True
    assert scrape_token_matches("Bearer anything", None) is True
    assert scrape_token_matches("Metrics s3cret", "s3cret") is True
    assert scrape_token_matches("metrics   s3cret ", "s3cret") is True
    assert scrape_token_matches("Bearer s3cret", "s3cret") is False
    assert scrape_token_matches("Metrics wrong", "s3cret") is False
    assert scrape_token_matches(None, "s3cret") is False
