"""Indonesian academic-specific lint rules and presets.

These rules check Indonesian academic document conventions like KP
(Kerja Praktik) reports, skripsi (undergraduate thesis), and tesis
(master's thesis). The rules subclass the generic
:class:`RequiredSectionRule` and provide an Indonesian-specific
``required_section_pattern``. Presets for ``academic_id``,
``academic_id_kp``, and ``academic_id_skripsi`` are registered at the
bottom of this module.
"""

from __future__ import annotations

from .base import LintRule, add_preset, register_rule
from .rules import RequiredSectionRule


# ── required-section rules for Indonesian KP / Skripsi ──


@register_rule
class RequiredSectionLembarPengesahanRule(RequiredSectionRule):
    id = "required_section_lembar_pengesahan"
    severity = "error"
    required_section_pattern = r"\b(lembar\s+)?pengesahan\b"
    section_label = "LEMBAR PENGESAHAN"


@register_rule
class RequiredSectionKataPengantarRule(RequiredSectionRule):
    id = "required_section_kata_pengantar"
    severity = "error"
    required_section_pattern = r"\bkata\s+pengantar\b"
    section_label = "KATA PENGANTAR"


@register_rule
class RequiredSectionDaftarIsiRule(RequiredSectionRule):
    id = "required_section_daftar_isi"
    severity = "error"
    required_section_pattern = r"\bdaftar\s+isi\b"
    section_label = "DAFTAR ISI"


@register_rule
class RequiredSectionDaftarPustakaRule(RequiredSectionRule):
    id = "required_section_daftar_pustaka"
    severity = "error"
    required_section_pattern = r"\b(daftar\s+pustaka|references|bibliography)\b"
    section_label = "DAFTAR PUSTAKA"


@register_rule
class RequiredSectionAbstrakRule(RequiredSectionRule):
    id = "required_section_abstrak"
    severity = "error"
    required_section_pattern = r"\babstrak\b"
    section_label = "ABSTRAK"


@register_rule
class RequiredSectionDaftarGambarRule(RequiredSectionRule):
    id = "required_section_daftar_gambar"
    severity = "warn"
    required_section_pattern = r"\bdaftar\s+gambar\b"
    section_label = "DAFTAR GAMBAR"


@register_rule
class RequiredSectionDaftarTabelRule(RequiredSectionRule):
    id = "required_section_daftar_tabel"
    severity = "warn"
    required_section_pattern = r"\bdaftar\s+tabel\b"
    section_label = "DAFTAR TABEL"


@register_rule
class RequiredSectionLampiranRule(RequiredSectionRule):
    id = "required_section_lampiran"
    severity = "warn"
    required_section_pattern = r"\blampiran\b"
    section_label = "LAMPIRAN"


@register_rule
class RequiredSectionPendahuluanRule(RequiredSectionRule):
    id = "required_section_pendahuluan"
    severity = "error"
    required_section_pattern = r"\bpendahuluan\b|\bbab\s+i\b"
    section_label = "BAB I PENDAHULUAN"


@register_rule
class RequiredSectionTinjauanPustakaRule(RequiredSectionRule):
    id = "required_section_tinjauan_pustaka"
    severity = "error"
    required_section_pattern = r"\btinjauan\s+pustaka\b|\blandasan\s+teori\b"
    section_label = "TINJAUAN PUSTAKA"


@register_rule
class RequiredSectionMetodologiRule(RequiredSectionRule):
    id = "required_section_metodologi"
    severity = "error"
    required_section_pattern = r"\bmetod(?:ologi|e)\b"
    section_label = "METODOLOGI"


@register_rule
class RequiredSectionHasilPembahasanRule(RequiredSectionRule):
    id = "required_section_hasil_pembahasan"
    severity = "error"
    required_section_pattern = r"\bhasil\s+(?:dan\s+)?pembahasan\b"
    section_label = "HASIL DAN PEMBAHASAN"


@register_rule
class RequiredSectionKesimpulanSaranRule(RequiredSectionRule):
    id = "required_section_kesimpulan_saran"
    severity = "error"
    required_section_pattern = r"\bkesimpulan(?:\s+dan\s+saran)?\b"
    section_label = "KESIMPULAN DAN SARAN"


# Specific instance: rule for the LOG BOOK section in a KP report.
@register_rule
class RequiredSectionLogBookRule(RequiredSectionRule):
    id = "required_section_log_book"
    severity = "error"
    required_section_pattern = r"\blog\s*book\b|\bcatatan\s+harian\b"
    section_label = "LOG BOOK"


# ── presets ──

add_preset(
    "academic_id",
    extends="default",
    description="Indonesian academic paper structural standards",
    rules=[
        "title_case_id",
    ],
)


add_preset(
    "academic_id_kp",
    extends="academic_id",
    description="KP (Kerja Praktik) report standards (Indonesian universities)",
    rules=[
        "required_section_lembar_pengesahan",
        "required_section_kata_pengantar",
        "required_section_daftar_isi",
        "required_section_pendahuluan",
        "required_section_daftar_pustaka",
        "required_section_lampiran",
        "required_section_log_book",
    ],
)


add_preset(
    "academic_id_skripsi",
    extends="academic_id",
    description="Skripsi (undergraduate thesis) Indonesian standards",
    rules=[
        "required_section_lembar_pengesahan",
        "required_section_abstrak",
        "required_section_kata_pengantar",
        "required_section_daftar_isi",
        "required_section_daftar_gambar",
        "required_section_daftar_tabel",
        "required_section_pendahuluan",
        "required_section_tinjauan_pustaka",
        "required_section_metodologi",
        "required_section_hasil_pembahasan",
        "required_section_kesimpulan_saran",
        "required_section_daftar_pustaka",
        "required_section_lampiran",
    ],
)
