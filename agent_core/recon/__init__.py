"""
Recon — Competitor content intelligence module for the content-pipeline.

Ported from ReelRecon. Scrapes competitor reels/videos, transcribes them,
extracts content skeletons (hook/value/CTA), and bridges findings into
the content-pipeline's topic discovery system.

Usage:
    from agent_core.recon.scraper.instagram import InstaClient
    from agent_core.recon.skeleton_ripper import SkeletonRipperPipeline, create_job_config
    from agent_core.recon.bridge import generate_topics_from_skeletons
    from agent_core.recon.config import load_config
"""
