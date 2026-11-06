"""robots.txt parsing with Google's matching rules.

The standard library's ``urllib.robotparser`` uses first-match order and ignores
``*`` and ``$`` wildcards, so a common WordPress file (``Disallow: /wp-admin/`` and
``Allow: /wp-admin/admin-ajax.php``) gives the wrong answer. This module follows
RFC 9309 and Google's documentation: the most specific (longest) matching rule wins,
and on a tie ``Allow`` wins.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]

    @classmethod
    def build(cls, allow: bool, pattern: str) -> "Rule":
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        regex = ".*".join(re.escape(part) for part in body.split("*"))
        return cls(allow, pattern, re.compile(regex + ("$" if anchored else "")))

    def matches(self, path: str) -> bool:
        return self.regex.match(path) is not None


@dataclass(slots=True)
class Group:
    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)


@dataclass(slots=True)
class RobotsTxt:
    groups: list[Group] = field(default_factory=list)
    sitemaps: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str) -> "RobotsTxt":
        robots = cls()
        current: Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = Group()
                    robots.groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key == "sitemap":
                if value:
                    robots.sitemaps.append(value)
            elif key in ("allow", "disallow") and current is not None and value:
                current.rules.append(Rule.build(key == "allow", value))
        return robots

    def rules_for(self, agent: str) -> list[Rule]:
        """Rules of every group naming ``agent``, or of the ``*`` groups if none does."""
        agent = agent.lower()
        named = [g for g in self.groups if any(a != "*" and agent.startswith(a) for a in g.agents)]
        chosen = named or [g for g in self.groups if "*" in g.agents]
        return [rule for group in chosen for rule in group.rules]

    def can_fetch(self, url: str, agent: str = "*") -> bool:
        parts = urlsplit(url)
        path = parts.path or "/"
        if path == "/robots.txt":
            return True
        if parts.query:
            path = f"{path}?{parts.query}"
        best: Rule | None = None
        for rule in self.rules_for(agent):
            if not rule.matches(path):
                continue
            if (
                best is None
                or len(rule.pattern) > len(best.pattern)
                or (len(rule.pattern) == len(best.pattern) and rule.allow)
            ):
                best = rule
        return best is None or best.allow
