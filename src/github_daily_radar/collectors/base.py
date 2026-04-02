from abc import ABC, abstractmethod

from github_daily_radar.client import GitHubClient
from github_daily_radar.models import Candidate


class Collector(ABC):
    name = "collector"

    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    @abstractmethod
    def collect(self) -> list[Candidate]:
        raise NotImplementedError
