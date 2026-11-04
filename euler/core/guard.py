"""A local check for requests the assistant must decline.

The language model already refuses most harmful requests, but a small model
sometimes complies — and when it does, it complies in detail. A question as
short as "как убить" produced step-by-step advice on lethal methods, because
nothing between the user and the model objected.

This module is that objection. It runs before generation, so a 0.5B model is
never put in the position of having to refuse on its own judgement.

It is deliberately narrow. It matches clear-cut requests only — violence
against a person, self-harm, sexual content involving minors, weapon and
explosive construction, drug synthesis, attacks on systems the user does not
own. A mathematics question that merely contains a sensitive word ("задача про
взрыв", "рассчитать дозу лекарства") passes through untouched. Over-blocking a
maths tutor would be worse than the occasional weak answer; under-blocking is
how the screenshot happened.

Results are message keys, not prose: the interface renders them in the user's
own language, and self-harm gets a different, supportive message rather than a
flat refusal.
"""
from __future__ import annotations

import re

# (pattern, reason). Matched against the lower-cased request.
_RULES: tuple[tuple[str, str], ...] = (
    # ---------------------------------------------------------------- minors
    # Never negotiable, checked first.
    (r"\b(ребен|ребён|дет|детск|малолет|несовершеннолет|школьниц|школьник)\w*"
     r"[^.]{0,40}\b(секс|интим|эрот|раздева|голы|обнаж|порн)\w*",
     "guard.minors"),
    (r"\b(секс|порн|эрот)\w*[^.]{0,40}\b(ребен|ребён|дет|малолет|несовершеннолет)\w*",
     "guard.minors"),
    (r"\bchild\s*(porn|sexual)\w*|\bcp\b|\bloli\w*",
     "guard.minors"),

    # ------------------------------------------------------------ self-harm
    # Treated separately from violence: the answer is not "I can't" but a
    # short, kind redirect. Checked before the general violence rules so the
    # person gets the supportive message rather than the terse one.
    (r"\b(покончить|покончи)\w*\s*(с\s*собой|жизн\w*)",
     "guard.selfharm"),
    (r"\b(самоубий|суицид)\w*",
     "guard.selfharm"),
    # Self-harm needs the reflexive pronoun. "как убить" alone is a threat to
    # someone else, and treating it as a cry for help would be both wrong and
    # unhelpful — that phrasing is handled by the violence rules below.
    (r"\b(убить|умереть|повесит|отравит|порезат)\w*\s+себя\b",
     "guard.selfharm"),
    (r"\bкак\s+(мне\s+)?себя\s+(убить|порезат|отравит)\w*",
     "guard.selfharm"),
    (r"\bне\s+хочу\s+(больше\s+)?жить\b",
     "guard.selfharm"),
    (r"\b(kill\s+myself|suicide|end\s+my\s+life|self[- ]harm)\b",
     "guard.selfharm"),

    # ------------------------------------------------------------- violence
    # "как убить" with no object is the exact phrase that produced the
    # screenshot. The negative lookahead keeps the idiom "убить время"
    # ("to kill time") working, which is a normal thing to type.
    # "убить время" is an idiom meaning "to pass the time"; "убить себя" is
    # self-harm and was caught above. Everything else is a request for how to
    # take a life — the exact phrase from the screenshot.
    (r"\bкак\s+(мне\s+)?убить\b(?!\s*(время|час|скуку|день|себя))",
     "guard.violence"),
    (r"\bкак\s+(мне\s+)?(зарезат|застрелит|задушит|покалечит|избит)\w*",
     "guard.violence"),
    (r"\b(отравит|убит)\w*\s+(человек|людей|сосед|жен|муж|ребен|кого-то)\w*",
     "guard.violence"),
    (r"\b(способы|методы|способы\s+того)\s+(убийств|убить|лишить\s+жизни)\w*",
     "guard.violence"),
    (r"\bкак\s+(лишить\s+жизни|причинить\s+(вред|смерть))\w*",
     "guard.violence"),
    (r"\b(самый\s+)?(эффективн|быстр|безболезненн)\w*\s+способ\w*\s+"
     r"(убить|убийств|умертвить)",
     "guard.violence"),
    (r"\bкак\s+(скрыть|замести)\s+(следы\s+)?(труп|убийств|тело)\w*",
     "guard.violence"),
    (r"\bhow\s+(do\s+i\s+|to\s+)?(kill|murder|stab|strangle|poison)\b(?!\s+time)",
     "guard.violence"),
    (r"\b(best|easiest|most\s+effective)\s+way\s+to\s+(kill|murder)\b",
     "guard.violence"),
    (r"\bhow\s+to\s+get\s+away\s+with\s+(murder|killing)\b",
     "guard.violence"),

    # -------------------------------------------------------- sexual content
    (r"\b(секс|порн|эрот|интим)\w*[^.]{0,30}\b(сценари|рассказ|описани|инструкц)\w*",
     "guard.sexual"),
    (r"\b(напиши|опиши|расскажи)\w*[^.]{0,30}\bпорн\w*",
     "guard.sexual"),
    (r"\bexplicit\s+sexual\b|\bwrite\s+porn\w*",
     "guard.sexual"),

    # --------------------------------------------------------------- weapons
    # The verb must describe making something, and the object must be an agent
    # of mass harm. "как работает ядерный реактор" has no such verb.
    (r"\b(сдела|собра|изготов|синтез|приготов|свар|получ)\w*"
     r"[^.]{0,60}\b(бомб|взрывчат|детонатор|тротил|гексоген"
     r"|нитроглицерин|нервно-паралит|зарин|зоман|vx|рицин|биологическ\w* оружи)",
     "guard.weapons"),
    (r"\b(рецепт|инструкц)\w*[^.]{0,40}\b(бомб|взрывчат|детонатор|зарин|рицин)",
     "guard.weapons"),
    (r"\b(how to|instructions?|recipe|build|make|synthesi[sz]e|manufacture)\w*"
     r"[^.]{0,60}\b(bomb|explosive|ied|detonator|tnt|sarin|vx|ricin|nerve agent"
     r"|bioweapon|chemical weapon)",
     "guard.weapons"),
    (r"\b(оруж|автомат|пистолет|глушитель|ствол)\w*[^.]{0,40}"
     r"\b(самодельн|собра|изготов|передела|чертеж|схем)",
     "guard.weapons"),

    # ----------------------------------------------------------------- drugs
    (r"\b(как|инструкц|рецепт|синтез|изготов|приготов|свари)\w*"
     r"[^.]{0,50}\b(метамфетамин|амфетамин|кокаин|героин|лсд|mdma|экстази|мефедрон)",
     "guard.drugs"),
    (r"\b(synthesi[sz]e|manufacture|cook|make)\w*[^.]{0,50}"
     r"\b(meth|amphetamine|cocaine|heroin|lsd|mdma|fentanyl)",
     "guard.drugs"),

    # ----------------------------------------------------------------- cyber
    # "защитить свой сайт от sql-инъекций" is defensive: the verb decides.
    (r"\b(взлома|хакн|обойти защит|подобрать парол|ddos|брутфорс)\w*",
     "guard.cyber"),
    (r"\b(hack|ddos|brute[ -]?force|keylog|ransomware|exploit)\w*"
     r"[^.]{0,40}\b(сайт|сервер|чуж|жертв|банк|аккаунт|сеть|site|server|victim|account)",
     "guard.cyber"),
    (r"\b(напиши|создай|сгенерируй)\w*[^.]{0,40}\b(вирус|троян|шифровальщик|стилер|кейлоггер)",
     "guard.cyber"),
)


def check(request: str) -> str | None:
    """Return a message key when the request must be declined, else ``None``."""
    if not request:
        return None

    text = request.lower().replace("ё", "е")

    for pattern, reason in _RULES:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            return reason

    return None


def is_care(reason: str | None) -> bool:
    """True when the reply should be supportive rather than a refusal."""
    return bool(reason) and reason.startswith("guard.selfharm")


# --------------------------------------------------------------- profanity
# Display filter, not a refusal. A model sometimes echoes the user's wording
# back, and a maths answer containing obscenities reads as a bug in the app.
#
# Masking keeps the first and last letter, so the word stays recognisable as a
# censored word rather than turning into a different one.
_PROFANITY = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bху[йяеи]\w*", r"\bхуйн\w*", r"\bпизд\w*", r"\bбля\w*", r"\bблядь\b",
        r"\b[её]б[ауыо]\w*", r"\b[её]бан\w*", r"\bза[её]б\w*", r"\bна[её]б\w*",
        r"\bдолбо[её]б\w*", r"\bмуд[ао]\w*", r"\bмудак\w*",
        r"\bпидор\w*", r"\bпедик\w*", r"\bгандон\w*", r"\bзалуп\w*",
        r"\bсучар\w*", r"\bсучк\w*", r"\bсука\b", r"\bсуки\b", r"\bговн\w*",
        r"\bfuck\w*", r"\bshit\w*", r"\bbitch\w*", r"\bcunt\w*",
        r"\basshole\w*", r"\bdickhead\w*",
    )
)

_WORD = re.compile(r"[А-Яа-яЁёA-Za-z]+")


def mask_profanity(text: str) -> str:
    """Replace the middle of an obscene word with asterisks.

    Leaves short words alone: masking a three-letter word entirely would make
    the sentence unreadable, and there is nothing to hide in it.
    """
    if not text:
        return text

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        if len(word) < 4:
            return word
        if any(pattern.fullmatch(word) or pattern.match(word) for pattern in _PROFANITY):
            return word[0] + "*" * (len(word) - 2) + word[-1]
        return word

    return _WORD.sub(replace, text)


__all__ = ["check", "is_care", "mask_profanity"]
