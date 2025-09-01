from mark2mind.utils.exporters import to_camel_nospace as _camel


def node_slug(title: str | None) -> str:
    return _camel(title or "Untitled")
