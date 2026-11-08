#!/usr/bin/env python3
"""
Fix legacy Persian/Arabic fonts that break in Microsoft Word for Mac.

Many old Persian fonts (the B series such as B Zar and B Nazanin, the Mj_ series, ...)
define the OpenType features init/medi/fina but no 'isol'. Word for Mac then draws the
final form for a letter that should stand alone, e.g. «سازمان» shows as «سازماز» and
«ریال» as «ریاا». This tool adds an 'isol' feature that maps every such letter to its
own base glyph. Glyph outlines, metrics, names and cmap are left untouched.

Usage:
    python3 fix_persian_fonts.py                 # scan the default macOS font folders
    python3 fix_persian_fonts.py --dry-run       # only list the fonts that need fixing
    python3 fix_persian_fonts.py path/to/fonts   # fix fonts in a folder (or single files)
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

try:
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables import otTables as ot
except ImportError:
    sys.exit('fontTools is required:  python3 -m pip install fonttools')

DEFAULT_DIRS = [os.path.expanduser('~/Library/Fonts'), '/Library/Fonts']
FONT_EXT = ('.ttf', '.otf')


def needs_fix(font):
    """True for a legacy font: Arabic fina without isol, and no GDEF (modern fonts carry GDEF and render fine)."""
    if 'GSUB' not in font or 'GDEF' in font:
        return False
    gsub = font['GSUB'].table
    if not gsub.FeatureList or not gsub.ScriptList:
        return False
    tags = {fr.FeatureTag for fr in gsub.FeatureList.FeatureRecord}
    scripts = {sr.ScriptTag for sr in gsub.ScriptList.ScriptRecord}
    return 'arab' in scripts and 'fina' in tags and 'isol' not in tags


def add_isol(font):
    """Append an identity 'isol' lookup and register it for every Arabic language system."""
    gsub = font['GSUB'].table
    fl, ll = gsub.FeatureList, gsub.LookupList

    # every glyph that has a final form also needs an isolated form: its own base glyph
    bases = set()
    for fr in fl.FeatureRecord:
        if fr.FeatureTag == 'fina':
            for i in fr.Feature.LookupListIndex:
                for st in ll.Lookup[i].SubTable:
                    if hasattr(st, 'mapping'):
                        bases.update(st.mapping.keys())
    if not bases:
        return 0

    sub = ot.SingleSubst()
    sub.mapping = {g: g for g in sorted(bases, key=font.getGlyphID)}
    lookup = ot.Lookup()
    lookup.LookupType, lookup.LookupFlag, lookup.SubTable, lookup.SubTableCount = 1, 1, [sub], 1
    ll.Lookup.append(lookup)
    ll.LookupCount = len(ll.Lookup)

    feature = ot.Feature()
    feature.FeatureParams, feature.LookupListIndex, feature.LookupCount = None, [ll.LookupCount - 1], 1
    record = ot.FeatureRecord()
    record.FeatureTag, record.Feature = 'isol', feature

    # FeatureList must stay sorted by tag; remap the indices every language system uses
    old = fl.FeatureRecord
    new = sorted(old + [record], key=lambda r: r.FeatureTag)
    remap = {i: new.index(r) for i, r in enumerate(old)}
    fl.FeatureRecord, fl.FeatureCount = new, len(new)
    isol_index = new.index(record)
    for sr in gsub.ScriptList.ScriptRecord:
        systems = [sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []
        systems += [lr.LangSys for lr in sr.Script.LangSysRecord]
        for ls in systems:
            idx = [remap[i] for i in ls.FeatureIndex]
            if sr.ScriptTag == 'arab':
                idx.append(isol_index)
            ls.FeatureIndex, ls.FeatureCount = sorted(idx), len(idx)
    return len(bases)


def collect(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(FONT_EXT):
                    yield os.path.join(p, name)
        elif os.path.isfile(p) and p.lower().endswith(FONT_EXT):
            yield p


def main():
    ap = argparse.ArgumentParser(description='Add the missing isol feature to legacy Persian fonts.')
    ap.add_argument('paths', nargs='*', help='font files or folders (default: macOS font folders)')
    ap.add_argument('--dry-run', action='store_true', help='only list fonts that need fixing')
    ap.add_argument('--backup', default=None, help='backup folder (default: ~/Desktop/persian-font-backup-<date>)')
    args = ap.parse_args()

    paths = args.paths or [d for d in DEFAULT_DIRS if os.path.isdir(d)]
    backup = args.backup or os.path.expanduser(f'~/Desktop/persian-font-backup-{datetime.now():%Y%m%d-%H%M%S}')
    fixed, failed, skipped_perm = [], [], []

    for path in collect(paths):
        try:
            font = TTFont(path)
            if not needs_fix(font):
                continue
            family = font['name'].getDebugName(1) or os.path.basename(path)
        except Exception:
            continue
        if args.dry_run:
            fixed.append((path, family))
            continue
        if not os.access(path, os.W_OK):
            skipped_perm.append(path)
            continue
        try:
            os.makedirs(backup, exist_ok=True)
            shutil.copy2(path, os.path.join(backup, os.path.basename(path)))
            n = add_isol(font)
            tmp = path + '.tmp-fix'
            font.save(tmp)
            os.replace(tmp, path)
            fixed.append((path, family))
            print(f'  fixed  {family}  ({os.path.basename(path)}, {n} letters)')
        except Exception as e:
            failed.append((path, str(e)))

    print()
    if args.dry_run:
        print(f'{len(fixed)} font file(s) need fixing:')
        for path, family in fixed:
            print(f'  {family}  ({path})')
        return
    print(f'Fixed {len(fixed)} font file(s).')
    if fixed:
        print(f'Originals backed up to: {backup}')
        print('Quit and reopen Word (and other Office apps) to see the change.')
    if skipped_perm:
        print(f'\n{len(skipped_perm)} file(s) skipped (no write permission, e.g. /Library/Fonts):')
        for p in skipped_perm:
            print('  ' + p)
        print('Run again with sudo to fix those.')
    if failed:
        print(f'\n{len(failed)} file(s) failed:')
        for p, e in failed:
            print(f'  {p}: {e}')


if __name__ == '__main__':
    main()
