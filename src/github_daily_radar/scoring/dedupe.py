from github_daily_radar.models import Candidate


def should_reenter(candidate: Candidate) -> bool:
    metrics = candidate.metrics

    if metrics.previous_star_growth_7d > 0:
        if metrics.star_growth_7d >= metrics.previous_star_growth_7d * 2:
            return True

    if metrics.has_new_release and metrics.days_since_previous_release is not None:
        if metrics.days_since_previous_release >= 7:
            return True

    if metrics.comment_growth_rate >= 0.5:
        return True

    return False
