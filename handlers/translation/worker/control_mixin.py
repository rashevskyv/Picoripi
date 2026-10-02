import time
import uuid
from typing import Dict, List, Optional
from utils.logging_utils import log_debug


class AIWorkerControlMixin:
    """Cancel and AI traffic logging."""

    def _log_ai_traffic(self, messages: List[Dict[str, str]], response_text: Optional[str] = None, error=None, chunk: Optional[int] = None):
        """Record one request, or the response/error that answers it.

        Call it with ``messages`` alone when the request goes out, and with the
        same list object plus ``response_text`` or ``error`` when it comes back:
        the two records then share a request id and the second carries the
        duration. ``error`` may be the exception itself.
        """
        from utils.logging_utils import log_ai_traffic
        key = id(messages)
        duration_ms = None
        if response_text is None and error is None:
            request_id = uuid.uuid4().hex[:8]
            self._traffic_open[key] = (request_id, time.monotonic())
        else:
            request_id, started = self._traffic_open.pop(key, (None, None))
            if started is not None:
                duration_ms = int((time.monotonic() - started) * 1000)
                kind = getattr(error, "kind", None) if error is not None else None
                self._traffic_done.append((duration_ms, getattr(kind, "value", kind) if error is not None else None, error is not None))
        log_ai_traffic(
            self.mw,
            self.task_details.get('type', 'unknown'),
            messages,
            response_text,
            error,
            request_id=request_id,
            chunk=chunk,
            attempt=self.task_details.get('attempt', 1),
            duration_ms=duration_ms,
        )

    def _traffic_summary(self) -> str:
        """One line on how the run's requests went, or '' when there were none."""
        done = list(self._traffic_done)
        if not done:
            return ""
        durations = sorted(duration for duration, _, _ in done)

        def percentile(share: float) -> float:
            return durations[min(len(durations) - 1, int(len(durations) * share))] / 1000.0

        text = f"{len(done)} request(s), p50 {percentile(0.5):.1f}s, p95 {percentile(0.95):.1f}s"
        failures: Dict[str, int] = {}
        for _, kind, failed in done:
            if failed:
                failures[kind or "other"] = failures.get(kind or "other", 0) + 1
        if failures:
            text += "; failed: " + ", ".join(f"{kind}×{count}" for kind, count in sorted(failures.items()))
        return text

    def _add_retry_reminder(self, messages: List[Dict[str, str]]) -> None:
        """On a retry, tell the model what was actually wrong with its last answer.

        Appended to the end of the system message, so the cacheable part of the
        prompt before it stays unchanged.
        """
        if self.task_details.get('attempt', 1) <= 1 or not isinstance(messages, list):
            return
        reason = str(self.task_details.get('last_error') or '').strip() or "the response could not be used"
        reminder = (
            "\n\nRETRY: your previous response to this request was rejected.\n"
            f"Reason: {reason[:600]}\n"
            "Correct exactly that and return the complete response in the required JSON format."
        )
        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'system':
                msg['content'] = msg.get('content', '') + reminder
                break

    def _report_traffic_summary(self) -> None:
        """Log the run's request statistics and, for a multi-request run, show them."""
        summary = self._traffic_summary()
        if not summary:
            return
        from utils.logging_utils import ai_traffic_enabled, write_ai_traffic_record
        log_debug(f"AIWorker: {summary}")
        if ai_traffic_enabled(self.mw):
            write_ai_traffic_record({"task": self.task_details.get('type', 'unknown'), "event": "summary", "summary": summary})
        if len(self._traffic_done) > 1:
            self.detail_updated.emit(summary)

    def cancel(self):
        """Cancel."""
        log_debug("AIWorker: Cancellation requested.")
        self.is_cancelled = True
        cancel_stream = getattr(self.provider, "cancel_active_stream", None)
        if callable(cancel_stream):
            cancel_stream()
