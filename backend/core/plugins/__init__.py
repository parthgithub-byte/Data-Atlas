from .github import analyze as github_analyze
from .reddit import analyze as reddit_analyze

PLUGINS = {
    "github": github_analyze,
    "reddit": reddit_analyze
}
