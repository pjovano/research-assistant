# Notation (extract-corpus, reference)

The script applies every rule below; the orchestrator decides nothing here.

**A math font is a font the text layer sets notation in.** `math_fonts.py`
judges a font, never a character: a font is a math font if its name is listed
(the Computer Modern math faces `CMMI`, `CMSY`, `CMEX`; `MathTime`; `stmary`;
`wasy`; `MSAM`, `MSBM`; `EUFM`, `EUSM`; `LASY`; `PazoMath`; `MathematicalPi`;
`Symbol`; `rsfs`; a name carrying `Math`), if at least half its characters are
neither letters, digits, nor punctuation, if it sets a mathematical symbol and
no letter at all, or if it is set one glyph at a time: at least 20 spans, at
least 85% of them one character, at least half its characters single letters,
and at most 5% of the work's characters. A ligature, a character that
decomposes into two or more letters (`ﬁ`, `ﬂ`), is never a single letter: a
font that sets only ligatures, one to a span, is a prose font.

**A notation page sets at least 5 characters that are in a math font or in a
Unicode arrow or mathematical operator block** (U+2190–22FF, U+27C0–27FF,
U+2900–2AFF, U+1D400–1D7FF). A Greek letter set in a prose font counts for
nothing: a Greek quotation is not notation.

**A notation page is read from pixels, and every other page from the text
layer.** The engine reads a notation page with its inline and displayed math
recognition on, and writes each formula as LaTeX.

**A notation span holds the engine's LaTeX and nothing else.** An inline
formula is written `$…$`, a displayed formula `$$…$$`. Control characters are
dropped from the LaTeX, and a formula left holding nothing is not written.

**The notation guard compares each formula's symbols with the text layer's
characters for the same stretch.** An inline formula's stretch is the text
layer's characters between the prose on either side of it, and a displayed
formula alone in its block takes the block's characters. If the prose on
either side cannot be matched, or two formulas meet with no prose between
them, the formula has no stretch and is flagged.

**The guard compares symbols, never their order or spacing.** Both sides are
folded before comparing: compatibility forms to their base (`ℒ` to `L`, `…` to
`...`), confusable forms to one form, overlays onto their base, blanks and
braces dropped. A bar followed by a tilde is one symbol, the snake turnstile,
and a bar followed by `=` is `⊨`. A font command, a structural command
(`\frac`, `\text`, `\quad`, an environment's name), and a sized delimiter
(`\left(`, `\bigl[`) contribute no symbol: the text layer draws a sized
delimiter as a shape, not a character.

| Symbols compared | Verdict | Written |
| --- | --- | --- |
| the same, each as often | agreed | the engine's LaTeX |
| as many on each side, differing in at most half the text layer's symbols or in one, in at most 2 kinds of substitution | corrected | the engine's LaTeX with each differing symbol replaced, in reading order, by the text layer's |
| any other difference, or no stretch | flagged | the engine's LaTeX |

A snake turnstile is written `\mid\!\sim`.

**A letter the text layer sets in one named alphabet takes that alphabet's
command.** If every occurrence of a letter in a formula's stretch is fraktur,
script, or double-struck, each occurrence the engine set in another alphabet
is corrected to `\mathfrak`, `\mathcal`, or `\mathbb`, and the formula is
corrected. If the stretch sets the letter in two alphabets, or the command
covers more than the one letter, the formula is flagged. If the text layer
names no alphabet for the letter, the engine's alphabet stands.

**A letter set in a fraktur, script, or double-struck font is written as that
alphabet's letter.** A font whose name carries `EUFM`, `EUFB`, `Fraktur`, or
`yfrak` is fraktur; one carrying `EUSM`, `EUSB`, `rsfs`, `MathScript`, or
`Calligraphic` is script, as is every capital of `CMSY` and `CMBSY`; one
carrying `MSBM`, `DoubleStruck`, or `bbold` is double-struck. The rule binds
both readings: the guard reads the alphabet from the letter, and a text-layer
chapter writes the letter the page shows.

**A dollar sign in prose is not a delimiter.** An inline span never opens on a
`$` followed by a blank or a digit, never closes on a `$` preceded by a blank
or followed by a digit, and never crosses a line break.

**A text-layer page writes the text layer's characters and no notation
span.** A combining overlay the page sets before its base is moved onto the
next character that is not a blank, and the pair is normalized: `̸` before `=`
is `≠`, and before `∈` is `∉`. Every ligature is written as its letters, and a
word broken by a hyphen at a line end is rejoined without the hyphen, unless
the document sets that word hyphenated inside a line.
