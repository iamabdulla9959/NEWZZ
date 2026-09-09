from datetime import datetime, timezone
from app.db import SessionLocal
from app.models import Card, CardSource, Source, StoryCluster, new_id

DEMO_STORIES = [
    {
        "category": "tech",
        "headline": "OpenAI and Anthropic Unveil Advanced Reasoning Benchmarks for Frontier Models",
        "summary": (
            "Leading artificial intelligence research laboratories have released standardized benchmarks aimed at "
            "evaluating mathematical problem solving and multi-step autonomous planning in frontier models. "
            "The new evaluation suite incorporates stringent adversarial validation protocols to measure factual accuracy "
            "and prevent hallucination patterns across specialized scientific domains. Technical auditors confirmed that "
            "transparent testing frameworks will become publicly accessible to academic institutions starting next month."
        ),
        "district": None,
        "state": None,
        "sources": [
            {"name": "BBC Technology", "url": "https://www.bbc.com/technology/ai-benchmarks", "trust_tier": 1},
            {"name": "Reuters Tech", "url": "https://www.reuters.com/technology/frontier-models-eval", "trust_tier": 1},
        ],
    },
    {
        "category": "international",
        "headline": "Global Clean Energy Investments Surpass Record Two Trillion Dollars in Annual Milestone",
        "summary": (
            "International energy authorities announced that global investments in renewable infrastructure and solar installations "
            "reached an unprecedented milestone this year. Cross-border capital expenditures across solar, offshore wind, and next-generation "
            "battery storage exceeded historical projections. Policy analysts emphasized that sustained fiscal incentives and grid modernizations "
            "have accelerated industrial adoption while lowering generation costs for developing economies worldwide."
        ),
        "district": None,
        "state": None,
        "sources": [
            {"name": "Reuters World", "url": "https://www.reuters.com/world/clean-energy-two-trillion", "trust_tier": 1},
            {"name": "BBC World", "url": "https://www.bbc.com/news/world-energy-milestone", "trust_tier": 1},
        ],
    },
    {
        "category": "national",
        "headline": "High-Speed Rail Corridor Expansion Approved to Connect Major Metropolitan Economic Hubs",
        "summary": (
            "Government officials have formally approved the next construction phase for the high-speed passenger rail corridor connecting "
            "major economic centers. The multi-billion dollar transportation project will feature upgraded signaling infrastructure, "
            "energy-efficient electric trainsets, and elevated viaduct segments designed to withstand extreme weather conditions. Transport "
            "authorities stated that passenger transit times between key metropolitan hubs will be reduced by nearly sixty percent."
        ),
        "district": None,
        "state": None,
        "sources": [
            {"name": "The Hindu National", "url": "https://www.thehindu.com/news/national/rail-corridor-expansion", "trust_tier": 2},
            {"name": "Reuters India", "url": "https://www.reuters.com/world/india/rail-expansion-metropolitan", "trust_tier": 1},
        ],
    },
    {
        "category": "state",
        "headline": "Tamil Nadu Launches State-Wide Micro-Grid Initiative for Sustainable Rural Electrification",
        "summary": (
            "The state administration in Tamil Nadu has inaugurated an ambitious clean power program establishing decentralized solar micro-grids "
            "across rural communities. The initiative integrates high-capacity lithium storage stations with automated load-balancing management "
            "to guarantee uninterrupted electricity for farming pumps and public healthcare clinics. Regional engineers confirmed that sixty villages "
            "have successfully transitioned to the resilient community network."
        ),
        "district": "Chennai",
        "state": "Tamil Nadu",
        "sources": [
            {"name": "The Hindu Tamil Nadu", "url": "https://www.thehindu.com/news/national/tamil-nadu/microgrid-initiative", "trust_tier": 2},
            {"name": "Example Gazette", "url": "https://example.invalid/gazette/tamil-nadu-power", "trust_tier": 2},
        ],
    },
    {
        "category": "district",
        "headline": "Chennai Metro Phase Two Testing Commences on Underground Corridor Network",
        "summary": (
            "Engineers and safety inspectors began dynamic testing on the subterranean track sections of Chennai Metro Phase Two today. "
            "Trial runs evaluated emergency braking responses, automated platform screen door synchronization, and tunnel ventilation efficiency "
            "under simulated operational load. Metropolitan transit authorities confirmed that commercial passenger services across the newly "
            "completed segment remain on track for inauguration later this year."
        ),
        "district": "Chennai",
        "state": "Tamil Nadu",
        "sources": [
            {"name": "The Hindu Tamil Nadu", "url": "https://www.thehindu.com/news/cities/chennai/metro-phase-two-trial", "trust_tier": 2},
            {"name": "Example Herald", "url": "https://example.invalid/herald/chennai-metro", "trust_tier": 2},
        ],
    },
    {
        "category": "science",
        "headline": "Space Telescope Discovers Atmospheric Water Vapor Signatures on Temperate Exoplanet",
        "summary": (
            "Astrophysicists analyzing high-resolution transmission spectra from deep space telescopes have detected unambiguous water vapor signatures "
            "in the atmosphere of a temperate rocky exoplanet orbiting within its host star's habitable zone. Planetary scientists noted that infrared spectroscopic "
            "data revealed dense cloud decks and potential photochemical haze layers. Further telescopic observations will attempt to constrain methane and carbon dioxide ratios."
        ),
        "district": None,
        "state": None,
        "sources": [
            {"name": "BBC World", "url": "https://www.bbc.com/news/science-exoplanet-atmosphere", "trust_tier": 1},
            {"name": "Reuters World", "url": "https://www.reuters.com/science/space-telescope-exoplanet", "trust_tier": 1},
        ],
    },
    {
        "category": "district",
        "headline": "Greater Chennai Corporation Announces Special Civic Works and Monsoon Readiness Drive",
        "summary": (
            "The municipal administration in Chennai has initiated targeted desilting and storm-water drainage upgrades "
            "across vulnerable neighborhood zones ahead of the seasonal monsoon. District engineers confirmed that "
            "twenty-four rapid action response teams with heavy pumping machinery have been stationed at low-lying intersections. "
            "Civic authorities requested residents to report water stagnation via the municipal toll-free helpline."
        ),
        "district": "Chennai",
        "state": "Tamil Nadu",
        "verification_type": "official_source",
        "sources": [
            {
                "name": "District Administration Chennai - Official Press Releases",
                "url": "https://chennai.nic.in/press-release/monsoon-readiness",
                "trust_tier": "official_local",
            },
        ],
    },
]


def seed_demo():
    db = SessionLocal()
    existing_headlines = {c.headline for c in db.query(Card).all()}

    count = 0
    for s in DEMO_STORIES:
        if s["headline"] in existing_headlines:
            continue

        cluster = StoryCluster(
            id=new_id(),
            title_hint=s["headline"],
            eligible=True,
            flagged_conflict=False,
        )
        db.add(cluster)
        db.flush()

        card = Card(
            id=new_id(),
            cluster_id=cluster.id,
            headline=s["headline"],
            summary=s["summary"],
            category=s["category"],
            verified_status="published",
            verification_type=s.get("verification_type", "cross_verified"),
            district=s["district"],
            state=s["state"],
            published_at=datetime.now(timezone.utc),
            created_by="seed",
        )

        db.add(card)
        db.flush()

        for src in s["sources"]:
            card_source = CardSource(
                id=new_id(),
                card_id=card.id,
                source_id=cluster.id,  # foreign key or cluster ref
                name=src["name"],
                url=src["url"],
                trust_tier=str(src["trust_tier"]),
            )
            # Find an existing source or link properly
            db_source = db.query(Source).filter(Source.name == src["name"]).first()
            if db_source:
                card_source.source_id = db_source.id
            else:
                new_src = Source(
                    id=new_id(),
                    name=src["name"],
                    category=s["category"],
                    rss_url=src["url"],
                    trust_tier=src["trust_tier"],
                    is_active=True,
                )
                db.add(new_src)
                db.flush()
                card_source.source_id = new_src.id

            db.add(card_source)

        count += 1

    db.commit()
    print(f"Seeded {count} demo cards. Total published cards: {db.query(Card).filter(Card.verified_status == 'published').count()}")


if __name__ == "__main__":
    seed_demo()
