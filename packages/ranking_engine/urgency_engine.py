"""
Urgency Engine.
Calculates temporal urgency (0..100) based on active real-world event state:
whether an event is developing, requires immediate public action, or has already concluded.
"""

import re
from typing import Optional, Tuple


class UrgencyEngine:
    @staticmethod
    def calculate_urgency(
        title: str,
        summary: str,
        is_developing: Optional[bool] = None,
        action_required: Optional[bool] = None,
        llm_urgency: Optional[float] = None,
        llm_reason: Optional[str] = None,
    ) -> Tuple[float, str]:
        """
        Computes the urgency score (0..100) and rationale.
        Considers active threat state, evacuation orders, and live developments.
        """
        if llm_urgency is not None and 0.0 <= llm_urgency <= 100.0:
            reason = llm_reason or "Assessed based on live situational development"
            return round(float(llm_urgency), 2), reason

        combined = f"{title} {summary}".lower()

        # Contextual check: Is this an isolated incident (e.g. single traffic accident, local crime, individual fatality)?
        is_isolated_incident = bool(
            re.search(
                r"\b(car (hit|crash|accident)|bike accident|motorcycle|scooter|auto-rickshaw|"
                r"truck (hit|collided|overturned)|bus collided|hit-and-run|pedestrian (hit|killed)|"
                r"road accident|traffic mishap|suicide|local crime|theft|murder suspect arrested|"
                r"stabbed in fight|body found|fatal accident)\b",
                combined
            )
            and not re.search(
                r"\b(flood|cyclone|earthquake|tsunami|landslide|avalanche|evacuat|chemical spill|"
                r"toxic|terror attack|mass casualty|dozens|hundreds|thousands|train derailment|plane crash)\b",
                combined
            )
        )

        if llm_urgency is not None and 0.0 <= llm_urgency <= 100.0:
            # Prevent hallucinated/dramatic LLM tags from granting emergency urgency to isolated incidents
            if is_isolated_incident and llm_urgency >= 70.0:
                return 35.0, "Isolated local incident; urgency adjusted to routine level"
            reason = llm_reason or "Assessed based on live situational development"
            return round(float(llm_urgency), 2), reason

        # 1. Very High: Active Emergency / Immediate Public Action Needed (90..100)
        # Requires genuine active public-safety hazard, mass evacuation, active disaster
        if (
            re.search(
                r"\b(evacuat(e|ion|ing)|take shelter|red alert|danger level|curfew imposed|"
                r"do not travel|immediate danger|emergency diversions? in effect|emergency declared|declared an emergency|"
                r"state of emergency|flooding|flash flood|dam breach|cyclone warning|toxic plume)\b",
                combined
            )
            or (action_required and not is_isolated_incident)
        ):
            return 95.0, "Immediate public action or safety precaution required right now"

        # 2. High: Rapidly Developing Crisis / Active Search & Rescue for mass incidents (75..89)
        if (
            re.search(
                r"\b(search and rescue|toll expected to rise|firefighters battling|"
                r"active shooter|hostage|developing crisis|death toll rises|"
                r"emergency room diversions?|ambulances diverted)\b",
                combined
            )
            or (is_developing and not is_isolated_incident)
        ) and not is_isolated_incident:
            return 82.0, "Critical situation currently unfolding with active emergency response"

        # 3. Medium-High: Breaking Announcement / Major Decision Today (50..74)
        if re.search(r"\b(today|hours ago|just in|breaking|approves|announces new|verdict delivered|signed agreement)\b", combined):
            return 60.0, "Significant real-time announcement or confirmed today"

        # 4. Moderate: Ongoing Controlled Situation / Routine Proceedings / Local Incidents (30..49)
        if is_isolated_incident:
            return 35.0, "Isolated local incident under routine handling"

        if re.search(r"\b(investigation ongoing|probe ordered|review scheduled|trial continues|monitored|committee)\b", combined):
            return 40.0, "Ongoing institutional procedure under official monitoring"

        # 5. Low: Retrospective / Historical / Commentary / Danger Passed (0..29)
        if re.search(r"\b(years ago|anniversary|reminisces|historic lookback|op-ed|editorial|opinion|review of)\b", combined):
            return 15.0, "Retrospective analysis, feature, or commentary"

        return 35.0, "Standard informational news update"
