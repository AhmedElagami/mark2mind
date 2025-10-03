from .chunk import ChunkStage
from .qa import QAStage
from .tree import TreeStage
from .cluster import ClusterStage
from .merge import MergeStage
from .refine import RefineStage
from .map_content import MapContentStage
from .qa_from_markdown import QAFromMarkdownStage
from .import_markmap import ImportMarkmapStage
from .enrich_notes import EnrichMarkmapNotesStage
from .bullets import BulletsStage
from .reformat import ReformatTextStage
from .clean_for_map import CleanForMapStage
from .subtitles import SubtitlesListStage, SubtitlesMergeStage


STAGE_REGISTRY = {
    "chunk": ChunkStage,
    "qa": QAStage,
    "tree": TreeStage,
    "cluster": ClusterStage,
    "merge": MergeStage,
    "refine": RefineStage,
    "map": MapContentStage,
    "qa_parse": QAFromMarkdownStage,
    "import_markmap": ImportMarkmapStage,
    "enrich_markmap_notes": EnrichMarkmapNotesStage,
    "bullets": BulletsStage,
    "reformat": ReformatTextStage,
    "clean_for_map": CleanForMapStage,
    "subs_list": SubtitlesListStage,
    "subs_merge": SubtitlesMergeStage,
}


__all__ = [
    "ChunkStage",
    "QAStage",
    "TreeStage",
    "ClusterStage",
    "MergeStage",
    "RefineStage",
    "MapContentStage",
    "QAFromMarkdownStage",
    "ImportMarkmapStage",
    "EnrichMarkmapNotesStage",
    "BulletsStage",
    "ReformatTextStage",
    "CleanForMapStage",
    "SubtitlesListStage",
    "SubtitlesMergeStage",
    "STAGE_REGISTRY",
]
