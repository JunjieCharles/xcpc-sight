"""Generate pinned 2026 preliminary school ranking video assets, offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from core import DefaultNormalizer, load_school_aliases, normalize_srk_contest
from scripts.school_ranking import SchoolStanding, school_standings

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ("icpc2026preliminary-1", "results-20260919", "94656957302009856",
     "8ca3ddf111c255b352021678000f4bac0040aa3e3f2cd827fd2fdc260f0dbd0b"),
    ("icpc2026preliminary-2", "results-20260919", "94656957834690560",
     "a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9"),
    ("ccpc2026preliminary", "results-20260923", "95451702349623296",
     "d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1"),
)
SIZE = (600, 1040)
MAX_CARD_TEAMS = 7


def ranks_text(ranks: tuple[int | None, ...]) -> str:
    return "/".join("—" if r is None else f"#{r}" for r in ranks)


def fit_font(text: str, path: Path, size: int, width: int) -> ImageFont.FreeTypeFont:
    while size >= 14:
        font = ImageFont.truetype(str(path), size)
        if font.getlength(text) <= width:
            return font
        size -= 1
    raise ValueError(f"text too long for card: {text}")


def render_card(
    row: SchoolStanding, logo_path: Path, regular: Path, bold: Path,
) -> Image.Image:
    card = Image.new("RGB", SIZE, "white")
    draw = ImageDraw.Draw(card)
    with Image.open(logo_path) as source:
        logo = source.convert("RGBA")
    white = Image.new("RGBA", logo.size, "white")
    logo = Image.alpha_composite(white, logo).convert("RGB")
    bbox = ImageChops.difference(logo, Image.new("RGB", logo.size, "white")).getbbox()
    if bbox:
        logo = logo.crop(bbox)
    scale = min(470 / logo.width, 440 / logo.height)
    logo = logo.resize((round(logo.width * scale), round(logo.height * scale)),
                       Image.Resampling.LANCZOS)
    card.paste(logo, ((600 - logo.width) // 2, 22 + (440 - logo.height) // 2))
    draw.rectangle((0, 480, 600, 562), fill="#5425bc")
    title = f"#{row.rank}  ({ranks_text(row.ranks)})"
    draw.text((300, 521), title, fill="white", anchor="mm",
              font=fit_font(title, bold, 45, 552))
    draw.rectangle((0, 563, 600, 680), fill="#bdd2fa")
    draw.text((300, 620), row.school, fill="#121827", anchor="mm",
              font=fit_font(row.school, bold, 63, 550))
    shown = row.teams[:MAX_CARD_TEAMS]
    count = len(shown)
    height = 42
    y = 864 - (count - 1) * height / 2
    rank_font = ImageFont.truetype(str(regular), 28)
    # Fixed slots across every card, including absences.
    rank_rights = (394, 482, 570)
    separators = (405, 493)
    name_width = 262
    for team in shown:
        # Share a baseline even when a long name needs a smaller font.
        draw.text((30, y), team.name, fill="#182032", anchor="ls",
                  font=fit_font(team.name, bold, 32, name_width))
        for right, rank in zip(rank_rights, team.ranks, strict=True):
            text = "—" if rank is None else f"#{rank}"
            draw.text((right, y), text, fill="#313d57", anchor="rs", font=rank_font)
        for x in separators:
            draw.text((x, y), "/", fill="#8991a2", anchor="ms", font=rank_font)
        y += height
    mask = Image.new("L", SIZE)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 599, 1039), radius=30, fill=255)
    card = card.convert("RGBA")
    card.putalpha(mask)
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logos", type=Path, default=ROOT / "assets/school-logos")
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--bold-font", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "video-scripts/2026-2027"
                        / "2026网络赛高校综合排名TOP50")
    args = parser.parse_args()
    normalizer = DefaultNormalizer(school_aliases=load_school_aliases(
        ROOT / "config/school-aliases.json"))
    contests, sources = [], []
    for contest_id, directory, file_id, sha in INPUTS:
        raw = (ROOT / f"data-cache/{directory}/{contest_id}.srk.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f"{contest_id}: SHA-256 mismatch")
        contests.append(normalize_srk_contest(
            json.loads(raw), contest_uk=contest_id,
            series="ccpc2026" if contest_id.startswith("ccpc") else "icpc2026",
        ))
        sources.append({"contestId": contest_id, "sha256": sha,
                        "url": f"https://cdn.algoux.cn/rankland/file/{file_id}"
                               f"/{contest_id}.srk.json"})
    rows = school_standings(tuple(contests), normalizer)
    selected = [r for r in rows if r.rank <= 50]
    logos = {}
    for path in sorted(args.logos.glob("*.png")):
        logos.setdefault(normalizer.school(path.stem), path)
    missing = [r.school for r in selected if normalizer.school(r.school) not in logos]
    if missing:
        raise ValueError(f"missing school logos: {missing}")
    cards_dir = args.output / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for row in selected:
        logo = logos[normalizer.school(row.school)]
        card = render_card(row, logo, args.font, args.bold_font)
        name = re.sub(r'[<>:"/\\|?*]', "_", row.school)
        card.save(cards_dir / f"{row.rank:02d}_{name}.png")
        rendered.append(card)
    for start in range(0, len(rendered), 10):
        sheet = Image.new("RGB", (2000, 1440), "#182032")
        draw = ImageDraw.Draw(sheet)
        last_rank = selected[min(start + 9, len(selected) - 1)].rank
        title = f"2026 网络赛高校综合排名 · #{selected[start].rank}–#{last_rank}"
        draw.text((60, 40), title, fill="white", font=fit_font(title, args.bold_font, 38, 1880))
        for offset, card in enumerate(rendered[start:start + 10]):
            thumb = card.resize((360, 624), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (60 + offset % 5 * 385, 112 + offset // 5 * 660), thumb)
        sheet.save(args.output / f"preview_{start+1:02d}-{min(start+10,len(rendered)):02d}.jpg",
                   quality=95, subsampling=0)
    document = {"sources": sources, "contestOrder": [c.contest_id for c in contests],
                "maxCardTeams": MAX_CARD_TEAMS, "schools": [asdict(r) for r in rows]}
    (args.output / "ranking.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output / "ranking.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["综合排名", "学校", "ICPC第一场校排", "ICPC第二场校排", "CCPC校排"])
        for row in rows:
            writer.writerow([row.rank, row.school, *row.ranks])
    (args.output / "README.md").write_text(
        "# 2026 网络赛高校综合排名 TOP50\n\n"
        f"共 {len(selected)} 张卡片，600×1040 RGBA PNG，透明圆角，白色卡面。\n\n"
        "`cards/` 按综合名次命名，倒序导入即可从第 50 名揭晓至第 1 名。"
        "`preview_*.jpg` 是十校一页的预览；`ranking.csv` 和 `ranking.json` 保存完整排名。\n\n"
        "色带括号内、队伍成绩的顺序均为：ICPC 第一场 / ICPC 第二场 / CCPC。"
        "色带为学校排名，下方为队伍总排名；— 表示没有对应有效成绩。\n\n"
        "每场取本校最佳正式队伍成绩计算校排，比较三个校排从小到大排序后的元组，"
        "依次比较最佳、次佳、第三。三项全同则并列。排除打星、无提交和官方移除的结果。\n\n"
        "队伍列出任一场队伍总排名进入前100的阵容；没有则取各场校内最佳阵容并集。"
        "候选按三场队伍排名的最佳、次佳、第三排序，卡片最多展示前7队，JSON 保留全部候选。"
        "跨场按同校完整成员集合匹配，"
        "不按队名猜测；阵容变化分开列出，改名展示最后一次有效队名。\n\n"
        "榜单版本核验日期：2026-09-23。来源 URL 和 SHA-256 见 ranking.json。"
        "校徽位于仓库 assets/school-logos。生成命令及规则见仓库 doc/school-ranking-cards.md。\n",
        encoding="utf-8",
    )
    print(f"Generated {len(selected)} cards; {len(rows)} schools; output: {args.output}")


if __name__ == "__main__":
    main()
