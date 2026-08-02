from __future__ import annotations

from pathlib import Path
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


NOTES_REL_TYPE_SUFFIX = '/notesSlide'
SLIDE_TITLE_PATTERN = re.compile(r'^\s*Slide:\s*(.+?)\s*$', re.IGNORECASE)
SLUG_SEPARATOR_PATTERN = re.compile(r'[^a-z0-9]+')


def slugify_slide_title(title: str) -> str:
    normalized = unicodedata.normalize('NFKD', title.strip())
    ascii_title = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = SLUG_SEPARATOR_PATTERN.sub('_', ascii_title.lower()).strip('_')
    return slug


def _relationship_target_for_type(archive: zipfile.ZipFile, rels_path: str, type_suffix: str) -> str | None:
    if rels_path not in archive.namelist():
        return None

    root = ET.fromstring(archive.read(rels_path))
    for relationship in root:
        rel_type = relationship.get('Type', '')
        if not rel_type.endswith(type_suffix):
            continue

        target = relationship.get('Target')
        if not target:
            return None

        slide_path = rels_path.replace('/_rels/', '/').removesuffix('.rels')
        return posixpath.normpath(posixpath.join(posixpath.dirname(slide_path), target))

    return None


def _notes_paragraphs(archive: zipfile.ZipFile, notes_path: str) -> list[str]:
    if notes_path not in archive.namelist():
        return []

    root = ET.fromstring(archive.read(notes_path))
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if not paragraph.tag.endswith('}p'):
            continue

        text = ''.join(
            text_node.text or ''
            for text_node in paragraph.iter()
            if text_node.tag.endswith('}t')
        ).strip()
        if text:
            paragraphs.append(text)

    return paragraphs


def _slide_title_from_notes(paragraphs: list[str]) -> str | None:
    for paragraph in paragraphs:
        match = SLIDE_TITLE_PATTERN.match(paragraph)
        if not match:
            continue

        slug = slugify_slide_title(match.group(1))
        if slug:
            return slug

    return None


def slide_output_stems_from_notes(pptx_path: Path, slide_count: int) -> list[str]:
    stems = [f'{slide_index:02d}' for slide_index in range(slide_count)]

    with zipfile.ZipFile(pptx_path) as archive:
        for slide_index in range(slide_count):
            slide_number = slide_index + 1
            rels_path = f'ppt/slides/_rels/slide{slide_number}.xml.rels'
            notes_path = _relationship_target_for_type(archive, rels_path, NOTES_REL_TYPE_SUFFIX)
            if notes_path is None:
                continue

            title_slug = _slide_title_from_notes(_notes_paragraphs(archive, notes_path))
            if title_slug:
                stems[slide_index] = f'{slide_index:02d}_{title_slug}'

    return stems
