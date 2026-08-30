"""Groq report provider — natural-language investigation reports using Groq API.

Groq is ONLY a natural-language explanation/reporting layer.
Groq MUST NOT:
- detect oil
- classify SAR pixels
- modify TinyUNet confidence
- calculate vessel attribution
- calculate drift
- determine guilt
- invent AIS observations
- invent environmental measurements
- invent coordinates
- invent dates
- override deterministic system results

All scientific computation happens before Groq is called.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.report_provider import GroqReportProvider, InvestigationReport

logger = logging.getLogger(__name__)

# System prompt enforcing strict evidence-based reporting
SYSTEM_PROMPT = """You are an investigation-reporting assistant for a maritime oil-spill decision-support system.

Use ONLY the structured evidence supplied to you.

Never invent information.
Never infer missing values.
Never change numerical values.
Never claim that a vessel caused an oil spill.
Use the phrase 'Potential Source Vessel'.
All vessel associations require human review.

Clearly distinguish:
- observed data
- model predictions
- heuristic evidence
- unavailable information

If AIS data is unavailable, say so.
If environmental forcing is DEMO, say so.
If confidence is not calibrated, say so.
If AIS gap analysis requires raw AIS and is unavailable, say so.

Do not present an evidence score as probability of guilt.
Do not claim certainty.

Return ONLY valid JSON matching this schema:
{
  "title": "string",
  "executiveSummary": "string",
  "detectionAssessment": "string",
  "environmentAssessment": "string",
  "driftAssessment": "string",
  "aisAssessment": "string",
  "candidateAssessments": [
    {
      "mmsi": "string",
      "vesselName": "string",
      "attributionScore": number,
      "explanation": "string"
    }
  ],
  "uncertainty": "string",
  "recommendedActions": ["string"],
  "limitations": ["string"],
  "humanReviewRequired": true
}"""


class GroqReportProviderImpl(GroqReportProvider):
    """Real Groq report provider using the Groq API."""

    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        if not api_key:
            raise ValueError(
                "Groq API key required: set GROQ_API_KEY in your .env file. "
                "Register at https://console.groq.com/"
            )
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Groq client."""
        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self._api_key)
            except ImportError:
                raise RuntimeError(
                    "groq package not installed. Run: pip install groq"
                )
        return self._client

    def generate_report(self, evidence_json: dict[str, Any]) -> InvestigationReport:
        """Generate investigation report using Groq API.

        Args:
            evidence_json: Serialized InvestigationEvidence.

        Returns:
            InvestigationReport with structured sections.

        Raises:
            RuntimeError: if API call fails or response validation fails.
        """
        client = self._get_client()

        user_message = (
            "Based on the following structured investigation evidence, "
            "generate a comprehensive investigation report.\n\n"
            "Evidence:\n" + json.dumps(evidence_json, indent=2, default=str)
        )

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Groq returned empty response")

            # Parse JSON response
            report_data = json.loads(content)

            # Validate and construct report
            return self._validate_report(report_data)

        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Groq returned invalid JSON: {exc}") from exc
        except Exception as exc:
            if "api_key" in str(exc).lower() or "auth" in str(exc).lower():
                raise RuntimeError(
                    f"Groq authentication failed: {exc}. "
                    "Check GROQ_API_KEY in .env"
                ) from exc
            raise RuntimeError(f"Groq report generation failed: {exc}") from exc

    def _validate_report(self, data: dict[str, Any]) -> InvestigationReport:
        """Validate and construct InvestigationReport from Groq response."""
        # Extract fields with defaults for missing values
        candidate_assessments = data.get("candidateAssessments", [])
        if not isinstance(candidate_assessments, list):
            candidate_assessments = []

        recommended_actions = data.get("recommendedActions", [])
        if not isinstance(recommended_actions, list):
            recommended_actions = [str(recommended_actions)] if recommended_actions else []

        limitations = data.get("limitations", [])
        if not isinstance(limitations, list):
            limitations = [str(limitations)] if limitations else []

        return InvestigationReport(
            title=str(data.get("title", "Investigation Report")),
            executive_summary=str(data.get("executiveSummary", "")),
            detection_assessment=str(data.get("detectionAssessment", "")),
            environment_assessment=str(data.get("environmentAssessment", "")),
            drift_assessment=str(data.get("driftAssessment", "")),
            ais_assessment=str(data.get("aisAssessment", "")),
            candidate_assessments=candidate_assessments,
            uncertainty=str(data.get("uncertainty", "")),
            recommended_actions=recommended_actions,
            limitations=limitations,
            human_review_required=bool(data.get("humanReviewRequired", True)),
        )

    def close(self) -> None:
        """Release resources."""
        self._client = None
