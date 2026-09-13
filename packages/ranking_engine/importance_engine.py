"""
Objective Importance Engine.
Calculates how much a real-world news event matters to the public (0..100).
Evaluates 8 distinct impact dimensions with strict boundary enforcement,
contextual evidence grounding, and conservative defaults for missing data.
"""

import re
from typing import Any, Dict, Optional
from .config import RankingConfig
from .models import DimensionEvidence, ObjectiveDimensions


class ImportanceEngine:
    @staticmethod
    def calculate_from_dimensions(dimensions: ObjectiveDimensions) -> float:
        """
        Calculates the total objective importance score from validated dimensions.
        Clamps each dimension strictly to its maximum limit and bounds total to 0..100.
        """
        human = min(dimensions.human_impact.score, RankingConfig.MAX_HUMAN_IMPACT)
        safety = min(dimensions.safety_impact.score, RankingConfig.MAX_SAFETY_IMPACT)
        geo = min(dimensions.geographic_impact.score, RankingConfig.MAX_GEOGRAPHIC_IMPACT)
        econ = min(dimensions.economic_impact.score, RankingConfig.MAX_ECONOMIC_IMPACT)
        policy = min(dimensions.policy_impact.score, RankingConfig.MAX_POLICY_IMPACT)
        infra = min(dimensions.infrastructure_impact.score, RankingConfig.MAX_INFRASTRUCTURE_IMPACT)
        security = min(dimensions.security_impact.score, RankingConfig.MAX_SECURITY_IMPACT)
        consequence = min(dimensions.consequence_impact.score, RankingConfig.MAX_CONSEQUENCE_IMPACT)

        total = human + safety + geo + econ + policy + infra + security + consequence
        return round(max(0.0, min(RankingConfig.TOTAL_OBJECTIVE_MAX, total)), 2)

    @classmethod
    def analyze_event_text(
        cls,
        title: str,
        summary: str,
        category: str = "national",
        llm_dimensions: Optional[Dict[str, Any]] = None,
    ) -> tuple[ObjectiveDimensions, float]:
        """
        Synthesizes structured dimensions and objective importance.
        If LLM dimensions are provided, validates and clamps them against evidence.
        Otherwise, applies deterministic contextual evidence extraction.
        """
        if llm_dimensions and isinstance(llm_dimensions, dict):
            dims = cls._parse_llm_dimensions(llm_dimensions)
            total = cls.calculate_from_dimensions(dims)
            return dims, total

        # Deterministic Contextual Extraction Fallback
        dims = cls._deterministic_extraction(title, summary, category)
        total = cls.calculate_from_dimensions(dims)
        return dims, total

    @classmethod
    def _parse_llm_dimensions(cls, raw: Dict[str, Any]) -> ObjectiveDimensions:
        """Parses and validates LLM-provided dimension scores and evidence."""
        dims = ObjectiveDimensions()

        def extract_field(key: str, max_val: float) -> DimensionEvidence:
            data = raw.get(key)
            if isinstance(data, dict):
                score = float(data.get("score", 0.0))
                evidence = str(data.get("evidence", "")).strip()
                explanation = str(data.get("explanation", "")).strip()
                conf = float(data.get("confidence", 0.9))
                return DimensionEvidence(
                    score=max(0.0, min(max_val, score)),
                    evidence=evidence,
                    confidence=max(0.0, min(1.0, conf)),
                    explanation=explanation,
                )
            elif isinstance(data, (int, float)):
                return DimensionEvidence(
                    score=max(0.0, min(max_val, float(data))),
                    evidence="Direct model evaluation",
                    confidence=0.8,
                    explanation="",
                )
            return DimensionEvidence(score=0.0, evidence="Insufficient evidence", confidence=0.5)

        dims.human_impact = extract_field("human_impact", RankingConfig.MAX_HUMAN_IMPACT)
        dims.safety_impact = extract_field("safety_impact", RankingConfig.MAX_SAFETY_IMPACT)
        dims.geographic_impact = extract_field("geographic_impact", RankingConfig.MAX_GEOGRAPHIC_IMPACT)
        dims.economic_impact = extract_field("economic_impact", RankingConfig.MAX_ECONOMIC_IMPACT)
        dims.policy_impact = extract_field("policy_impact", RankingConfig.MAX_POLICY_IMPACT)
        dims.infrastructure_impact = extract_field("infrastructure_impact", RankingConfig.MAX_INFRASTRUCTURE_IMPACT)
        dims.security_impact = extract_field("security_impact", RankingConfig.MAX_SECURITY_IMPACT)
        dims.consequence_impact = extract_field("consequence_impact", RankingConfig.MAX_CONSEQUENCE_IMPACT)

        return dims

    WORD_TO_NUM = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50
    }

    CASUALTY_PATTERNS = [
        r"\bclaim(?:s|ed)?\s+(?:at least\s+)?(?P<count>[0-9,]+)\s+lives\b",
        r"\bdeath toll\s+(?:of|at|rises to|reaches|hits|stood at|climbs to)\s+(?:at least\s+)?(?P<count>[0-9,]+)\b",
        r"\bat least\s+(?P<count>[0-9,]+)\s+(?:people\s+|residents\s+|civilians\s+|passengers\s+|children\s+)?(?:have died|died|dead|killed|fatalities|deaths)\b",
        r"\b(?P<count>[0-9,]+)\s+(?:people\s+|residents\s+|civilians\s+|passengers\s+|children\s+)?(?:have died|died|dead|killed|fatalities|deaths|lives lost|lost their lives)\b",
        r"\b(?P<word>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty)\s+(?:people\s+|residents\s+|civilians\s+|passengers\s+|children\s+)?(?:have died|died|dead|killed|fatalities|deaths|lives lost)\b",
        r"\bclaim(?:s|ed)?\s+(?P<word>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+lives\b",
    ]

    @classmethod
    def _extract_casualty_count(cls, text: str) -> Optional[int]:
        """
        Extracts explicit casualty count from text, supporting integers and comma-separated numbers.
        Strictly avoids false positives from years (e.g. 2025), monetary amounts ($1,385 million),
        property/homes (1,385 homes), or vague affected counts (1,385 people affected).
        """
        lower = text.lower()
        for pat in cls.CASUALTY_PATTERNS:
            m = re.search(pat, lower)
            if m:
                gd = m.groupdict()
                if "count" in gd and gd["count"]:
                    raw = gd["count"].replace(",", "")
                    start, end = m.span("count")
                    prefix = lower[max(0, start - 5):start]
                    suffix = lower[end:min(len(lower), end + 12)]
                    if "$" in prefix or "rs" in prefix or "inr" in prefix:
                        continue
                    if "million" in suffix or "billion" in suffix or "crore" in suffix:
                        continue
                    try:
                        return int(raw)
                    except ValueError:
                        continue
                elif "word" in gd and gd["word"]:
                    return cls.WORD_TO_NUM.get(gd["word"])
        return None

    @classmethod
    def _deterministic_extraction(cls, title: str, summary: str, category: str) -> ObjectiveDimensions:
        """
        Extracts structured impact evidence from text context without guessing.
        Distinguishes context (e.g. celebrity death vs disaster casualties).
        """
        combined = f"{title} {summary}".lower()
        dims = ObjectiveDimensions()

        # 1. Human Impact (0..20)
        # Contextual check: Do NOT treat "actor dies" as mass human impact
        is_celebrity_or_single_death = bool(
            re.search(r"\b(actor|actress|star|singer|director|celebrity|author|aged \d+|at \d+)\b", combined)
            and not re.search(r"\b(thousands|hundreds|mass|displaced|injured|toll hits|killed in)\b", combined)
        )

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

        casualty_count = cls._extract_casualty_count(f"{title} {summary}")

        if casualty_count is not None:
            if casualty_count >= 1000:
                dims.human_impact = DimensionEvidence(score=20.0, evidence=f"Severe mass casualty event ({casualty_count:,} documented deaths)")
            elif casualty_count >= 100:
                dims.human_impact = DimensionEvidence(score=16.0, evidence=f"Hundreds of documented casualties ({casualty_count:,})")
            elif casualty_count >= 10:
                dims.human_impact = DimensionEvidence(score=12.0, evidence=f"Dozens of documented casualties ({casualty_count:,})")
            elif casualty_count >= 2:
                dims.human_impact = DimensionEvidence(score=8.0, evidence=f"Multiple documented casualties ({casualty_count:,})")
            elif casualty_count == 1:
                score_val = 2.0 if is_celebrity_or_single_death else (3.0 if is_isolated_incident else 6.0)
                dims.human_impact = DimensionEvidence(score=score_val, evidence=f"Single casualty documented ({casualty_count})")
        elif re.search(r"\b(millions|mass casualty|tens of thousands displaced)\b", combined):
            dims.human_impact = DimensionEvidence(score=20.0, evidence="Millions or massive population affected")
        elif re.search(r"\b(thousands displaced|thousands affected|thousands injured|hundreds dead|hundreds killed|toll hits \d{2,}|mandatory evacuation|evacuation order)\b", combined):
            dims.human_impact = DimensionEvidence(score=16.0, evidence="Thousands directly displaced/injured, hundreds dead, or mandatory evacuation")
        elif re.search(r"\b(\d{2,}\s+(killed|dead|fatalities|injured)|hundreds affected|hundreds injured|dozens dead)\b", combined):
            dims.human_impact = DimensionEvidence(score=12.0, evidence="Dozens to hundreds of casualties/affected")
        elif re.search(r"\b(emergency room diversions|patient monitoring offline|surgeries canceled|vulnerable population|hospital.*diversion)\b", combined):
            dims.human_impact = DimensionEvidence(score=12.0, evidence="Critical healthcare disruption directly jeopardizing patient care")
        elif re.search(r"\b(crash|accident killed)\b", combined) and not is_celebrity_or_single_death:
            score_val = 4.0 if is_isolated_incident else 8.0
            dims.human_impact = DimensionEvidence(score=score_val, evidence="Documented fatal accident")
        elif is_celebrity_or_single_death:
            dims.human_impact = DimensionEvidence(score=2.0, evidence="Individual notable passing; no public harm")
        else:
            dims.human_impact = DimensionEvidence(score=0.0, evidence="No mass casualty or displacement reported")

        # 2. Public Safety / Life (0..20)
        if re.search(r"\b(cyclone|earthquake|tsunami|flash flood|major flood|flooding|evacuat|landslide|toxic leak|chemical spill|toxic plume|state of emergency|emergency declared)\b", combined):
            dims.safety_impact = DimensionEvidence(score=18.0, evidence="Active natural disaster or life safety threat")
        elif re.search(r"\b(epidemic|virus outbreak|fire breaks out|building collapse|terror attack|strike on|emergency room diversion|ambulances diverted|patient.*offline)\b", combined):
            dims.safety_impact = DimensionEvidence(score=15.0, evidence="Serious acute danger to public life/safety")
        elif re.search(r"\b(warning issued|alert sounded|precautionary advisory|storm alert)\b", combined):
            dims.safety_impact = DimensionEvidence(score=10.0, evidence="Official alert or hazard warning in effect")
        elif re.search(r"\b(fatal collision|accident|encounter|arrested under sc/st)\b", combined):
            score_val = 3.0 if is_isolated_incident else 6.0
            dims.safety_impact = DimensionEvidence(score=score_val, evidence="Localized law enforcement or traffic safety incident")
        else:
            dims.safety_impact = DimensionEvidence(score=0.0, evidence="No immediate physical safety threat")

        # 3. Geographic / Scale (0..15)
        cat = category.lower()
        if is_isolated_incident:
            dims.geographic_impact = DimensionEvidence(score=2.0, evidence="Localized local traffic or safety incident")
        elif re.search(r"\b(global|international|world|nepal|cross-border|foreign|un security council|brics summit|unsc|multilateral|nato)\b", combined) or cat == "international":
            dims.geographic_impact = DimensionEvidence(score=14.0, evidence="International or multi-country scope")
        elif re.search(r"\b(nationwide|across india|union cabinet|parliament|prime minister|supreme court)\b", combined) or cat == "national":
            dims.geographic_impact = DimensionEvidence(score=11.0, evidence="National scale scope")
        elif re.search(r"\b(statewide|high court|chief minister|assembly|across the state|metropolitan)\b", combined) or cat == "state":
            dims.geographic_impact = DimensionEvidence(score=8.0, evidence="Statewide or metropolitan administrative scale")
        elif re.search(r"\b(district|city|municipal|panchayat|ward)\b", combined) or cat in ("district", "local"):
            dims.geographic_impact = DimensionEvidence(score=5.0, evidence="District or city level impact")
        else:
            dims.geographic_impact = DimensionEvidence(score=2.0, evidence="Localized or unverified scope")

        # 4. Economic Impact (0..10)
        if is_isolated_incident:
            dims.economic_impact = DimensionEvidence(score=0.0, evidence="No macroeconomic consequence")
        elif re.search(r"\b(market crash|sensex plunges|recession|gdp contracted|sanctions imposed|bank collapse|tariff war)\b", combined):
            dims.economic_impact = DimensionEvidence(score=9.0, evidence="Critical macro financial disruption")
        elif re.search(r"\b(union budget|interest rate|repo rate|inflation surges|tax bill|trade agreement|currency settlement|liquidity boost)\b", combined):
            dims.economic_impact = DimensionEvidence(score=7.0, evidence="Major national economic or trade policy")
        elif re.search(r"\b(derailment|chemical spill|toxic plume|hazardous waste|factory explosion|building collapse)\b", combined):
            dims.economic_impact = DimensionEvidence(score=5.0, evidence="Major industrial or disaster damage")
        elif re.search(r"\b(ipo opens|stock exchange|quarterly profit|revenue up|investment deal)\b", combined) and cat == "business":
            dims.economic_impact = DimensionEvidence(score=4.0, evidence="Routine commercial/business activity")
        else:
            dims.economic_impact = DimensionEvidence(score=0.0, evidence="No significant economic consequence")

        # 5. Government / Policy Impact (0..10)
        if re.search(r"\b(law passed|bill enacted|constitutional amendment|general election|ordinance promulgated)\b", combined):
            dims.policy_impact = DimensionEvidence(score=10.0, evidence="Statutory enactment or major election")
        elif re.search(r"\b(cabinet approves|policy unveiled|statutory framework|supreme court rules|high court refuses|treaty signed)\b", combined):
            dims.policy_impact = DimensionEvidence(score=7.0, evidence="Executive approval, treaty, or high court ruling")
        elif re.search(r"\b(assembly session|mlas suspended|protest march|party demands)\b", combined):
            dims.policy_impact = DimensionEvidence(score=3.0, evidence="Legislative debate or political positioning")
        else:
            dims.policy_impact = DimensionEvidence(score=0.0, evidence="No major legislative or executive policy shift")

        # 6. Infrastructure Impact (0..10)
        if re.search(r"\b(power grid|airports shut|flights grounded|railways halted|hospital.*(shut|paralyz|halt|network)|water supply cut|healthcare.*system|banking network|payment gateways?|building collapse)\b", combined):
            dims.infrastructure_impact = DimensionEvidence(score=9.0, evidence="Severe disruption to critical utilities, buildings, healthcare, or transit")
        elif re.search(r"\b(train derailment|derailment|metro services delayed|train collision|highway blocked|telecom outage)\b", combined):
            dims.infrastructure_impact = DimensionEvidence(score=8.0, evidence="Major transport corridor severance or train derailment")
        elif re.search(r"\b(pipeline maintenance|traffic diversion|road repairs)\b", combined):
            dims.infrastructure_impact = DimensionEvidence(score=2.0, evidence="Minor routine maintenance")
        else:
            dims.infrastructure_impact = DimensionEvidence(score=0.0, evidence="No public infrastructure failure")

        # 7. Security / Cyber Impact (0..10)
        if re.search(r"\b(cyberattack|ransomware|data breach|critical infrastructure hack|malware|ddos grid)\b", combined):
            if re.search(r"\b(hospital|health.*network|defense|power grid|bank|banking)\b", combined):
                dims.security_impact = DimensionEvidence(score=10.0, evidence="High-risk cyberattack on essential public sector")
            else:
                dims.security_impact = DimensionEvidence(score=7.0, evidence="Significant digital breach or cybersecurity threat")
        elif re.search(r"\b(terrorist encounter|militant neutralized|weapons recovered|ied blast|cross-border firing)\b", combined):
            dims.security_impact = DimensionEvidence(score=8.0, evidence="National security counter-terror operation")
        elif re.search(r"\b(poacher trap|theft arrested|contraband seized)\b", combined):
            dims.security_impact = DimensionEvidence(score=3.0, evidence="Routine criminal law enforcement")
        else:
            dims.security_impact = DimensionEvidence(score=0.0, evidence="No major security or cyber emergency")

        # 8. Long-Term Consequence (0..5)
        if re.search(r"\b(decade-long|generational|historic treaty|war declared|permanent shift|law will change)\b", combined):
            dims.consequence_impact = DimensionEvidence(score=5.0, evidence="Multi-year or permanent structural change")
        elif re.search(r"\b(bilateral pact|reconstruction|new declaration|summit outcome)\b", combined):
            dims.consequence_impact = DimensionEvidence(score=3.0, evidence="Medium-term geopolitical or economic impact")
        else:
            dims.consequence_impact = DimensionEvidence(score=0.0, evidence="Transient news cycle item")

        return dims
