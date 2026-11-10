"""Reference of standard theorems and formulas.

The list is not a shelf to browse: it is a retrieval corpus. The assistant
receives the entries that match the question and uses them as grounding, so the
answer rests on a correct statement instead of a hallucinated one.

Each entry carries:

    id        stable key
    area      algebra | trigonometry | geometry | stereometry | limits |
              derivatives | integrals | series | probability | complex
    level     school | university
    title     i18n key for the heading
    latex     the statement, ready to typeset
    example   a one-line worked example
    keywords  search terms in Russian and English

``rank()`` scores entries against a free-form question; ``search()`` filters by
area and level for the browse view that no longer exists but stays useful from
code.
"""
from __future__ import annotations

import math
import re

# (id, area, level, title, latex, example, keywords)
_RAW: list[tuple[str, str, str, str, str, str, str]] = [
    # ------------------------------------------------------------------ algebra
    ("vieta", "algebra", "school", "theorem.vieta",
     r"x^2 + px + q = 0:\quad x_1 + x_2 = -p,\;\; x_1 x_2 = q",
     r"x^2 - 5x + 6 = 0:\; 2 + 3 = 5,\; 2 \cdot 3 = 6",
     "виета vieta корни сумма произведение quadratic roots sum product"),
    ("quadratic", "algebra", "school", "theorem.quadratic",
     r"ax^2 + bx + c = 0:\quad x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
     r"x^2 - 5x + 6 = 0:\; D = 1,\; x = 3,\; 2",
     "формула корней квадратного уравнения discriminant quadratic formula"),
    ("discriminant-cases", "algebra", "school", "theorem.discriminant_cases",
     r"D > 0:\; 2 \text{ корня};\quad D = 0:\; 1 \text{ корень};\quad D < 0:\; \text{нет действительных}",
     r"x^2 + 1 = 0:\; D = -4 < 0",
     "дискриминант случаи корней discriminant cases roots"),
    ("factoring-quadratic", "algebra", "school", "theorem.factoring",
     r"ax^2 + bx + c = a(x - x_1)(x - x_2)",
     r"x^2 - 5x + 6 = (x - 2)(x - 3)",
     "разложение квадратного трехчлена множители factoring roots factor"),
    ("complete-square", "algebra", "school", "theorem.complete_square",
     r"ax^2 + bx + c = a\left(x + \frac{b}{2a}\right)^2 - \frac{b^2 - 4ac}{4a}",
     r"x^2 + 4x + 1 = (x + 2)^2 - 3",
     "выделение полного квадрата complete square vertex вершина парабола"),
    ("square-diff", "algebra", "school", "theorem.square_diff",
     r"a^2 - b^2 = (a - b)(a + b)",
     r"x^2 - 9 = (x - 3)(x + 3)",
     "разность квадратов difference of squares формулы сокращенного умножения"),
    ("cube-sum-diff", "algebra", "school", "theorem.cube_sum_diff",
     r"a^3 \pm b^3 = (a \pm b)(a^2 \mp ab + b^2)",
     r"x^3 - 8 = (x - 2)(x^2 + 2x + 4)",
     "сумма разность кубов cubes формулы сокращенного умножения"),
    ("binomial", "algebra", "school", "theorem.binomial",
     r"(a+b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^{k}",
     r"(x+2)^3 = x^3 + 6x^2 + 12x + 8",
     "бином ньютона binomial theorem степень раскрыть скобки"),
    ("binomial-series", "algebra", "university", "theorem.binomial_newton",
     r"(1+x)^{\alpha} = \sum_{k=0}^{\infty} \binom{\alpha}{k} x^k,\; |x| < 1",
     r"\sqrt{1+x} = 1 + \frac{x}{2} - \frac{x^2}{8} + \dots",
     "биномиальный ряд binomial series разложение корень"),
    ("log-definition", "algebra", "school", "theorem.log_definition",
     r"\log_a b = c \iff a^c = b,\quad a > 0,\; a \neq 1,\; b > 0",
     r"\log_2 8 = 3 \iff 2^3 = 8",
     "определение логарифма logarithm definition основание"),
    ("log-rules", "algebra", "school", "theorem.log_rules",
     r"\ln(ab) = \ln a + \ln b,\quad \ln\frac{a}{b} = \ln a - \ln b,\quad \ln a^n = n \ln a",
     r"\ln 8 = 3 \ln 2",
     "свойства логарифмов логарифм произведения степени logarithm rules"),
    ("power-rules", "algebra", "school", "theorem.power_rules",
     r"a^m a^n = a^{m+n},\quad \frac{a^m}{a^n} = a^{m-n},\quad (a^m)^n = a^{mn}",
     r"2^3 \cdot 2^4 = 2^7 = 128",
     "свойства степеней степень exponent rules powers"),
    ("arithmetic-progression", "algebra", "school", "theorem.arithmetic",
     r"a_n = a_1 + (n-1)d,\quad S_n = \frac{a_1 + a_n}{2}\, n",
     r"2, 5, 8, \dots:\; a_{10} = 29",
     "арифметическая прогрессия разность сумма arithmetic progression"),
    ("geometric-progression", "algebra", "school", "theorem.geometric",
     r"b_n = b_1 q^{n-1},\quad S_n = b_1 \frac{q^n - 1}{q - 1}",
     r"1, 2, 4, \dots:\; S_5 = 31",
     "геометрическая прогрессия знаменатель geometric progression"),
    ("geometric-infinite", "algebra", "school", "theorem.geometric_infinite",
     r"S = \frac{b_1}{1 - q},\quad |q| < 1",
     r"1 + \tfrac{1}{2} + \tfrac{1}{4} + \dots = 2",
     "бесконечная геометрическая сумма infinite geometric sum сходимость"),
    ("inverse-vieta", "algebra", "school", "theorem.inverse_vieta",
     r"x^2 - (x_1 + x_2)x + x_1 x_2 = 0",
     r"\text{корни } 2, 3:\; x^2 - 5x + 6 = 0",
     "обратная теорема виета составить уравнение по корням"),
    ("horner", "algebra", "university", "theorem.horner",
     r"P(x) = (x - a)Q(x) + P(a)",
     r"P(x) = x^3 - 2x + 4,\; P(2) = 8",
     "теорема безу горнер деление многочлена остаток bezout horner"),
    ("cramer", "algebra", "university", "theorem.cramer",
     r"x_i = \frac{\Delta_i}{\Delta},\quad \Delta \neq 0",
     r"\Delta = -2,\; \Delta_x = -6 \Rightarrow x = 3",
     "крамер определитель система линейных cramer rule determinant"),
    ("combinatorics-permutations", "algebra", "school", "theorem.permutations",
     r"P_n = n!",
     r"P_4 = 24",
     "перестановки факториал permutations factorial комбинаторика"),
    ("combinatorics-arrangements", "algebra", "school", "theorem.arrangements",
     r"A_n^k = \frac{n!}{(n-k)!}",
     r"A_5^2 = 20",
     "размещения arrangements комбинаторика выбор порядок"),
    ("combinatorics-combinations", "algebra", "school", "theorem.combinations",
     r"C_n^k = \frac{n!}{k!(n-k)!}",
     r"C_5^2 = 10",
     "сочетания combinations комбинаторика выбор без порядка"),
    ("compound-interest", "algebra", "school", "theorem.compound_interest",
     r"A = A_0\,(1 + p)^n",
     r"A_0 = 1000,\; p = 5\%,\; n = 3 \Rightarrow 1157{,}6",
     "сложные проценты вклад банк compound interest процент"),
    ("odz", "algebra", "school", "theorem.odz",
     r"\text{знаменатель} \neq 0,\quad \sqrt{f}:\; f \ge 0,\quad \log_a f:\; f > 0",
     r"\frac{1}{x-3}:\; x \neq 3",
     "одз область допустимых значений знаменатель корень логарифм domain"),
    ("interval-method", "algebra", "school", "theorem.interval_method",
     r"(x - a)(x - b) \lessgtr 0 \text{ по знаку на промежутках}",
     r"(x-2)(x-3) > 0:\; x \in (-\infty; 2) \cup (3; +\infty)",
     "метод интервалов неравенство знаки interval method inequality"),
    ("quadratic-inequality", "algebra", "school", "theorem.quadratic_inequality",
     r"ax^2 + bx + c > 0:\; \text{смотрим знак } a \text{ и корни}",
     r"x^2 - 5x + 6 > 0:\; x < 2 \text{ или } x > 3",
     "квадратное неравенство парабола ветви quadratic inequality"),

    # ------------------------------------------------------------ trigonometry
    ("pythagorean-identity", "trigonometry", "school", "theorem.pythagorean_identity",
     r"\sin^2 x + \cos^2 x = 1",
     r"\sin x = 0{,}6 \Rightarrow \cos x = \pm 0{,}8",
     "основное тригонометрическое тождество sin cos identity"),
    ("addition-sin", "trigonometry", "school", "theorem.addition_sin",
     r"\sin(\alpha \pm \beta) = \sin\alpha\cos\beta \pm \cos\alpha\sin\beta",
     r"\sin 75^\circ = \frac{\sqrt6 + \sqrt2}{4}",
     "синус суммы разности sine addition"),
    ("addition-cos", "trigonometry", "school", "theorem.addition_cos",
     r"\cos(\alpha \pm \beta) = \cos\alpha\cos\beta \mp \sin\alpha\sin\beta",
     r"\cos 2\alpha = \cos^2\alpha - \sin^2\alpha",
     "косинус суммы разности cosine addition"),
    ("double-angle", "trigonometry", "school", "theorem.double_angle",
     r"\sin 2x = 2\sin x\cos x,\quad \cos 2x = 1 - 2\sin^2 x",
     r"\sin 60^\circ = \frac{\sqrt3}{2}",
     "двойной угол double angle формулы"),
    ("half-angle", "trigonometry", "school", "theorem.half_angle",
     r"\sin^2\frac{x}{2} = \frac{1 - \cos x}{2},\quad \cos^2\frac{x}{2} = \frac{1 + \cos x}{2}",
     r"\sin^2 15^\circ = \frac{2 - \sqrt3}{4}",
     "половинный угол half angle понижение степени"),
    ("triple-angle", "trigonometry", "school", "theorem.triple_angle",
     r"\sin 3x = 3\sin x - 4\sin^3 x,\quad \cos 3x = 4\cos^3 x - 3\cos x",
     r"\sin 90^\circ = 3 - 4 = -1 + 2",
     "тройной угол triple angle"),
    ("sum-to-product", "trigonometry", "school", "theorem.sum_to_product",
     r"\sin\alpha + \sin\beta = 2\sin\frac{\alpha+\beta}{2}\cos\frac{\alpha-\beta}{2}",
     r"\sin 5x + \sin 3x = 2 \sin 4x \cos x",
     "сумма в произведение sum to product"),
    ("product-to-sum", "trigonometry", "school", "theorem.product_to_sum",
     r"\sin\alpha\cos\beta = \frac{1}{2}\big(\sin(\alpha+\beta) + \sin(\alpha-\beta)\big)",
     r"\sin 3x\cos x = \tfrac{1}{2}(\sin 4x + \sin 2x)",
     "произведение в сумму product to sum"),
    ("reduction-formulas", "trigonometry", "school", "theorem.reduction",
     r"\sin(\pi - x) = \sin x,\quad \cos(\pi - x) = -\cos x,\quad \sin\left(\frac{\pi}{2} + x\right) = \cos x",
     r"\cos 120^\circ = -\cos 60^\circ = -\tfrac{1}{2}",
     "формулы приведения reduction formulas пи"),
    ("general-sin", "trigonometry", "school", "theorem.general_sin",
     r"\sin x = a:\quad x = (-1)^n \arcsin a + \pi n,\; n \in \mathbb{Z}",
     r"\sin x = \tfrac{1}{2}:\; x = (-1)^n \tfrac{\pi}{6} + \pi n",
     "общее решение sin x = a тригонометрическое уравнение"),
    ("general-cos", "trigonometry", "school", "theorem.general_cos",
     r"\cos x = a:\quad x = \pm \arccos a + 2\pi n,\; n \in \mathbb{Z}",
     r"\cos x = \tfrac{1}{2}:\; x = \pm\tfrac{\pi}{3} + 2\pi n",
     "общее решение cos x = a тригонометрическое уравнение"),
    ("general-tan", "trigonometry", "school", "theorem.general_tan",
     r"\tan x = a:\quad x = \arctan a + \pi n,\; n \in \mathbb{Z}",
     r"\tan x = 1:\; x = \tfrac{\pi}{4} + \pi n",
     "общее решение tg x = a тригонометрическое уравнение"),
    ("values-table", "trigonometry", "school", "theorem.values_table",
     r"\sin 30^\circ = \tfrac{1}{2},\; \cos 30^\circ = \tfrac{\sqrt3}{2},\; \tan 45^\circ = 1",
     r"\sin 60^\circ = \tfrac{\sqrt3}{2}",
     "таблица значений синус косинус тангенс углы 30 45 60"),
    ("auxiliary-angle", "trigonometry", "school", "theorem.auxiliary",
     r"a\sin x + b\cos x = \sqrt{a^2+b^2}\,\sin(x + \varphi)",
     r"\sin x + \cos x = \sqrt2 \sin\left(x + \tfrac{\pi}{4}\right)",
     "вспомогательный угол auxiliary angle asinx+bcosx"),
    ("universal-substitution", "trigonometry", "university", "theorem.universal_substitution",
     r"t = \tan\frac{x}{2}:\quad \sin x = \frac{2t}{1+t^2},\;\; \cos x = \frac{1-t^2}{1+t^2}",
     r"\int \frac{dx}{\sin x} = \ln\left|\tan\frac{x}{2}\right|",
     "универсальная подстановка tangent half angle"),
    ("sine-rule", "trigonometry", "school", "theorem.sine_rule",
     r"\frac{a}{\sin A} = \frac{b}{\sin B} = \frac{c}{\sin C} = 2R",
     r"a = 7,\; A = 30^\circ \Rightarrow 2R = 14",
     "теорема синусов law of sines треугольник"),
    ("cosine-rule", "trigonometry", "school", "theorem.cosine_rule",
     r"c^2 = a^2 + b^2 - 2ab\cos C",
     r"a = b = 1,\; C = 60^\circ \Rightarrow c = 1",
     "теорема косинусов law of cosines треугольник"),
    ("arc-relations", "trigonometry", "school", "theorem.arc_relations",
     r"\arcsin x + \arccos x = \frac{\pi}{2},\quad \arctan x + \text{arcctg}\,x = \frac{\pi}{2}",
     r"\arcsin \tfrac{1}{2} = \tfrac{\pi}{6},\; \arccos \tfrac{1}{2} = \tfrac{\pi}{3}",
     "обратные тригонометрические arcsin arccos arctan связь"),

    # --------------------------------------------------------------- plane geometry
    ("pythagoras", "geometry", "school", "theorem.pythagoras",
     r"a^2 + b^2 = c^2",
     r"3^2 + 4^2 = 5^2",
     "пифагор гипотенуза катет прямоугольный pythagoras"),
    ("circle-area", "geometry", "school", "theorem.circle_area",
     r"S = \pi R^2,\quad L = 2\pi R",
     r"R = 3 \Rightarrow S = 9\pi",
     "площадь длина окружности круг радиус circle area circumference"),
    ("triangle-area", "geometry", "school", "theorem.triangle_area",
     r"S = \frac{1}{2}ab\sin C = \sqrt{p(p-a)(p-b)(p-c)}",
     r"3, 4, 5:\; p = 6,\; S = 6",
     "площадь треугольника герон heron triangle area"),
    ("median", "geometry", "school", "theorem.median",
     r"m_a = \frac{1}{2}\sqrt{2b^2 + 2c^2 - a^2}",
     r"a=4,\; b=c=5:\; m_a = \sqrt{21}",
     "медиана median треугольник"),
    ("bisector", "geometry", "school", "theorem.bisector",
     r"l_c = \frac{2ab\cos\frac{C}{2}}{a+b},\quad \frac{AL}{LB} = \frac{AC}{BC}",
     r"a=3,\; b=4,\; C=90^\circ:\; l \approx 2{,}4",
     "биссектриса bisector треугольник свойство"),
    ("height", "geometry", "school", "theorem.height",
     r"h_a = \frac{2S}{a} = b\sin C",
     r"S = 12,\; a = 6 \Rightarrow h = 4",
     "высота height треугольник площадь"),
    ("inradius", "geometry", "school", "theorem.inradius",
     r"r = \frac{S}{p} = \frac{a+b-c}{2}\;(\text{прямоугольный})",
     r"3,4,5:\; p=6,\; S=6,\; r=1",
     "радиус вписанной окружности inradius треугольник"),
    ("circumradius", "geometry", "school", "theorem.circumradius",
     r"R = \frac{abc}{4S} = \frac{a}{2\sin A}",
     r"3,4,5:\; R = 2{,}5",
     "радиус описанной окружности circumradius треугольник"),
    ("trapezoid", "geometry", "school", "theorem.trapezoid",
     r"S = \frac{a+b}{2}\,h",
     r"a=4,\; b=6,\; h=3 \Rightarrow S=15",
     "площадь трапеции trapezoid средняя линия"),
    ("parallelogram", "geometry", "school", "theorem.parallelogram",
     r"S = ah = ab\sin\alpha",
     r"a=5,\; h=3 \Rightarrow S=15",
     "площадь параллелограмма parallelogram"),
    ("rhombus", "geometry", "school", "theorem.rhombus",
     r"S = \frac{d_1 d_2}{2} = a^2 \sin\alpha",
     r"d_1=6,\; d_2=8 \Rightarrow S=24",
     "площадь ромба диагонали rhombus"),
    ("regular-polygon", "geometry", "school", "theorem.regular_polygon",
     r"S = \frac{1}{2} P r = \frac{n a^2}{4\tan\frac{\pi}{n}}",
     r"\text{квадрат } a=2:\; S=4",
     "правильный многоугольник площадь regular polygon"),
    ("sector", "geometry", "school", "theorem.sector",
     r"S = \frac{\alpha}{360^\circ}\pi R^2,\quad L = \frac{\alpha}{360^\circ}2\pi R",
     r"R=6,\; \alpha=60^\circ \Rightarrow S = 6\pi",
     "сектор круга площадь дуга sector arc"),
    ("segment", "geometry", "school", "theorem.segment",
     r"S = \frac{R^2}{2}(\alpha - \sin\alpha)",
     r"R=2,\; \alpha = \pi \Rightarrow S = 2\pi",
     "сегмент круга площадь segment"),
    ("chord", "geometry", "school", "theorem.chord",
     r"l = 2R\sin\frac{\alpha}{2},\quad d^2 = R^2 - \left(\frac{l}{2}\right)^2",
     r"R=5,\; l=6 \Rightarrow d=4",
     "хорда расстояние до центра chord"),
    ("power-of-point", "geometry", "school", "theorem.power_of_point",
     r"AB \cdot AC = AD \cdot AE,\quad t^2 = d^2 - R^2",
     r"AB=2,\; AC=8 \Rightarrow AD \cdot AE = 16",
     "степень точки касательная секущая power of a point tangent secant"),
    ("inscribed-angle", "geometry", "school", "theorem.inscribed_angle",
     r"\angle ABC = \frac{1}{2}\smile AC",
     r"\text{дуга } 80^\circ \Rightarrow 40^\circ",
     "вписанный угол дуга inscribed angle"),
    ("thales", "geometry", "school", "theorem.thales",
     r"\text{Вписанный угол на диаметр равен } 90^\circ",
     r"AB = 2R \Rightarrow \angle ACB = 90^\circ",
     "фалес диаметр прямой угол thales"),
    ("ptolemy", "geometry", "university", "theorem.ptolemy",
     r"d_1 d_2 = ac + bd \;(\text{вписанный четырёхугольник})",
     r"\text{квадрат со стороной } 1:\; \sqrt2\cdot\sqrt2 = 2",
     "птолемей вписанный четырехугольник ptolemy cyclic"),
    ("described-quadrilateral", "geometry", "school", "theorem.described_quad",
     r"a + c = b + d",
     r"3+5 = 4+4",
     "описанный четырехугольник суммы сторон described quadrilateral"),
    ("euler-line", "geometry", "university", "theorem.euler_line",
     r"OH^2 = 9R^2 - (a^2 + b^2 + c^2)",
     r"\text{равносторонний}: O = H",
     "эйлер прямая ортоцентр euler line"),
    ("distance-points", "geometry", "school", "theorem.distance_points",
     r"d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}",
     r"(0,0),(3,4):\; d = 5",
     "расстояние между точками координаты distance"),
    ("midpoint", "geometry", "school", "theorem.midpoint",
     r"M\left(\frac{x_1 + x_2}{2}; \frac{y_1 + y_2}{2}\right)",
     r"(0,0),(4,6):\; M(2;3)",
     "середина отрезка координаты midpoint"),
    ("line-equation", "geometry", "school", "theorem.line",
     r"y = kx + b,\quad k = \frac{y_2 - y_1}{x_2 - x_1}",
     r"A(1,2), B(3,6):\; k = 2",
     "уравнение прямой угловой коэффициент line slope"),
    ("circle-equation", "geometry", "school", "theorem.circle_equation",
     r"(x - a)^2 + (y - b)^2 = R^2",
     r"\text{центр } (1;2),\; R=3",
     "уравнение окружности координаты circle equation"),

    # ------------------------------------------------------------ solid geometry
    ("sphere", "stereometry", "school", "theorem.sphere",
     r"V = \frac{4}{3}\pi R^3,\quad S = 4\pi R^2",
     r"R = 3 \Rightarrow V = 36\pi",
     "сфера шар объем поверхность sphere volume"),
    ("cone", "stereometry", "school", "theorem.cone",
     r"V = \frac{1}{3}\pi R^2 h,\quad S = \pi R(R + l)",
     r"R=3,\; h=4,\; l=5 \Rightarrow V=12\pi",
     "конус объем образующая cone"),
    ("cylinder", "stereometry", "school", "theorem.cylinder",
     r"V = \pi R^2 h,\quad S = 2\pi R(R + h)",
     r"R=2,\; h=5 \Rightarrow V = 20\pi",
     "цилиндр объем cylinder"),
    ("prism", "stereometry", "school", "theorem.prism",
     r"V = S_{\text{осн}} \cdot h",
     r"S=6,\; h=5 \Rightarrow V=30",
     "призма объем prism параллелепипед"),
    ("pyramid", "stereometry", "school", "theorem.pyramid",
     r"V = \frac{1}{3} S_{\text{осн}} h",
     r"S=9,\; h=4 \Rightarrow V=12",
     "пирамида объем pyramid"),
    ("truncated-cone", "stereometry", "school", "theorem.truncated_cone",
     r"V = \frac{\pi h}{3}(R^2 + Rr + r^2)",
     r"R=3,\; r=1,\; h=3 \Rightarrow V = 13\pi",
     "усеченный конус объем truncated cone"),
    ("tetrahedron", "stereometry", "school", "theorem.tetrahedron",
     r"V = \frac{\sqrt2}{12}a^3",
     r"a=1 \Rightarrow V \approx 0{,}118",
     "тетраэдр правильный объем tetrahedron"),
    ("cube-diagonal", "stereometry", "school", "theorem.cube_diagonal",
     r"d = a\sqrt3,\quad V = a^3",
     r"a=2 \Rightarrow d = 2\sqrt3",
     "куб диагональ объем cube diagonal"),
    ("similar-solids", "stereometry", "school", "theorem.similar_solids",
     r"\frac{S_1}{S_2} = k^2,\quad \frac{V_1}{V_2} = k^3",
     r"k=2 \Rightarrow S \times 4,\; V \times 8",
     "подобие тел объем площадь коэффициент similar solids"),
    ("sphere-section", "stereometry", "university", "theorem.sphere_section",
     r"S = \pi(R^2 - d^2)",
     r"R=5,\; d=3 \Rightarrow S=16\pi",
     "сечение шара плоскость sphere section"),
    ("cone-section", "stereometry", "university", "theorem.cone_section",
     r"\text{осевое сечение — равнобедренный треугольник}",
     r"R=3,\; h=4 \Rightarrow l=5",
     "сечение конуса осевое cone section"),
    ("volume-ratio", "stereometry", "school", "theorem.volume_ratio",
     r"\frac{V_1}{V_2} = \left(\frac{a_1}{a_2}\right)^3",
     r"a_1:a_2 = 1:3 \Rightarrow V \text{ в } 27",
     "отношение объемов подобные тела volume ratio"),

    # ------------------------------------------------------------------ limits
    ("limit-definition", "limits", "university", "theorem.limit_definition",
     r"\lim_{x \to a} f(x) = L \iff \forall \varepsilon > 0\; \exists \delta > 0:\; |x-a| < \delta \Rightarrow |f(x)-L| < \varepsilon",
     r"\lim_{x \to 2} x^2 = 4",
     "определение предела эпсилон дельта limit definition epsilon"),
    ("first-limit", "limits", "school", "theorem.first_limit",
     r"\lim_{x \to 0} \frac{\sin x}{x} = 1",
     r"\lim_{x \to 0} \frac{\sin 3x}{x} = 3",
     "первый замечательный предел sin x x"),
    ("second-limit", "limits", "school", "theorem.second_limit",
     r"\lim_{x \to \infty}\left(1 + \frac{1}{x}\right)^x = e",
     r"\lim \left(1 + \frac{2}{x}\right)^x = e^2",
     "второй замечательный предел число e"),
    ("equivalents", "limits", "university", "theorem.equivalents",
     r"x \to 0:\; \sin x \sim x,\; \ln(1+x) \sim x,\; e^x - 1 \sim x,\; 1 - \cos x \sim \frac{x^2}{2}",
     r"\lim_{x\to0}\frac{1-\cos x}{x^2} = \frac{1}{2}",
     "эквивалентные бесконечно малые equivalents asymptotic"),
    ("lhopital", "limits", "university", "theorem.lhopital",
     r"\lim \frac{f}{g} = \lim \frac{f'}{g'},\quad \left[\frac{0}{0}\right], \left[\frac{\infty}{\infty}\right]",
     r"\lim_{x \to 0}\frac{\sin x}{x} = 1",
     "лопиталь правило предел неопределенность lhopital"),
    ("continuity", "limits", "university", "theorem.continuity",
     r"\lim_{x \to a^-} f = \lim_{x \to a^+} f = f(a)",
     r"f(x) = |x| \text{ непрерывна в } 0",
     "непрерывность разрыв continuity discontinuity"),
    ("asymptotes", "limits", "school", "theorem.asymptotes",
     r"k = \lim_{x\to\infty}\frac{f(x)}{x},\quad b = \lim_{x\to\infty}(f(x) - kx)",
     r"f(x) = \frac{1}{x}:\; x=0,\; y=0",
     "асимптота наклонная вертикальная asymptote"),
    ("taylor", "limits", "university", "theorem.taylor",
     r"f(x) = \sum_{k=0}^{n} \frac{f^{(k)}(a)}{k!}(x-a)^k + R_n(x)",
     r"e^x = 1 + x + \frac{x^2}{2} + \dots",
     "тейлор формула разложение taylor"),
    ("maclaurin", "limits", "university", "theorem.maclaurin",
     r"\sin x = x - \frac{x^3}{6} + \frac{x^5}{120} - \dots",
     r"\sin 0{,}1 \approx 0{,}09983",
     "маклорен ряд разложение maclaurin"),
    ("rolle", "limits", "university", "theorem.rolle",
     r"f(a) = f(b) \Rightarrow \exists c \in (a,b):\; f'(c) = 0",
     r"f(x) = x^2 \text{ на } [-1,1]:\; c = 0",
     "ролль теорема rolles theorem производная ноль"),
    ("lagrange-mean", "limits", "university", "theorem.lagrange_mean",
     r"\exists c:\; f'(c) = \frac{f(b) - f(a)}{b - a}",
     r"f(x) = x^2 \text{ на } [0,2]:\; c = 1",
     "лагранж теорема о среднем приращение lagrange mean value theorem"),
    ("cauchy-mean", "limits", "university", "theorem.cauchy_mean",
     r"\frac{f'(c)}{g'(c)} = \frac{f(b) - f(a)}{g(b) - g(a)}",
     r"f = x^2,\; g = x \text{ на } [0,2]:\; c = 1",
     "коши теорема о среднем обобщённая cauchy mean value"),
    ("fermat", "limits", "university", "theorem.fermat",
     r"\text{в точке экстремума } f'(c) = 0",
     r"f(x) = x^2:\; f'(0) = 0,\; \min = 0",
     "ферма теорема экстремум производная ноль fermat theorem"),
    ("lipschitz", "limits", "university", "theorem.lipschitz",
     r"|f(x) - f(y)| \le L|x - y|",
     r"|\sin x - \sin y| \le |x - y|",
     "липшиц условие непрерывность lipschitz condition"),
    ("one-sided", "limits", "university", "theorem.one_sided",
     r"\lim_{x \to a^-} f \neq \lim_{x \to a^+} f \Rightarrow \text{предела нет}",
     r"\frac{1}{x}:\; -\infty \text{ и } +\infty",
     "односторонний предел слева справа one-sided limit"),

    # ------------------------------------------------------------- derivatives
    ("derivative-definition", "derivatives", "school", "theorem.derivative_definition",
     r"f'(x) = \lim_{\Delta x \to 0} \frac{f(x + \Delta x) - f(x)}{\Delta x}",
     r"(x^2)' = 2x",
     "определение производной приращение derivative definition"),
    ("product-rule", "derivatives", "school", "theorem.product_rule",
     r"(uv)' = u'v + uv'",
     r"(x\sin x)' = \sin x + x\cos x",
     "правило произведения производная product rule"),
    ("quotient-rule", "derivatives", "school", "theorem.quotient_rule",
     r"\left(\frac{u}{v}\right)' = \frac{u'v - uv'}{v^2}",
     r"\left(\frac{\sin x}{x}\right)' = \frac{x\cos x - \sin x}{x^2}",
     "правило частного производная quotient rule"),
    ("chain-rule", "derivatives", "school", "theorem.chain_rule",
     r"\big(f(g(x))\big)' = f'(g(x)) \cdot g'(x)",
     r"(\sin 3x)' = 3\cos 3x",
     "сложная функция цепочка производная chain rule"),
    ("derivative-table", "derivatives", "school", "theorem.derivative_table",
     r"(\sin x)' = \cos x,\; (\ln x)' = \frac{1}{x},\; (e^x)' = e^x,\; (\sqrt{x})' = \frac{1}{2\sqrt{x}}",
     r"(5\ln x - 2e^x)' = \frac{5}{x} - 2e^x",
     "таблица производных derivative table"),
    ("second-derivative", "derivatives", "university", "theorem.second_derivative",
     r"f''(x) = (f'(x))'",
     r"(x^3)'' = 6x",
     "вторая производная second derivative"),
    ("extrema-first", "derivatives", "school", "theorem.extrema_first",
     r"f' \text{ меняет } + \to -:\; \max;\quad - \to +:\; \min",
     r"f(x)=x^2:\; f'=2x \Rightarrow \min \text{ в } 0",
     "экстремум максимум минимум первая производная extremum"),
    ("extrema-second", "derivatives", "university", "theorem.extrema_second",
     r"f'(c)=0,\; f''(c) > 0 \Rightarrow \min;\quad f''(c) < 0 \Rightarrow \max",
     r"f(x)=x^2:\; f''=2>0 \Rightarrow \min",
     "достаточное условие экстремума вторая производная"),
    ("convexity", "derivatives", "university", "theorem.convexity",
     r"f'' > 0 \Rightarrow \text{выпукла вниз};\quad f'' < 0 \Rightarrow \text{вверх}",
     r"f(x)=x^2:\; f''=2>0",
     "выпуклость вогнутость точка перегиба convexity inflection"),
    ("implicit", "derivatives", "university", "theorem.implicit",
     r"F(x,y)=0:\quad y' = -\frac{F_x}{F_y}",
     r"x^2+y^2=1:\; y' = -\frac{x}{y}",
     "неявная функция производная implicit differentiation"),
    ("parametric", "derivatives", "university", "theorem.parametric",
     r"x = x(t),\; y = y(t):\quad y'_x = \frac{y'_t}{x'_t}",
     r"x=\cos t,\; y=\sin t:\; y' = -\cot t",
     "параметрическая производная parametric derivative"),
    ("partial-derivative", "derivatives", "university", "theorem.partial",
     r"\frac{\partial f}{\partial x},\quad df = f_x\,dx + f_y\,dy",
     r"f=x^2y:\; f_x = 2xy,\; f_y = x^2",
     "частная производная дифференциал partial derivative"),

    # --------------------------------------------------------------- integrals
    ("newton-leibniz", "integrals", "school", "theorem.newton_leibniz",
     r"\int_a^b f(x)\,dx = F(b) - F(a)",
     r"\int_0^1 x^2 dx = \frac{1}{3}",
     "ньютон лейбниц определенный интеграл newton leibniz"),
    ("parts", "integrals", "university", "theorem.parts",
     r"\int u\,dv = uv - \int v\,du",
     r"\int x e^x dx = x e^x - e^x + C",
     "по частям интегрирование parts"),
    ("substitution", "integrals", "school", "theorem.substitution",
     r"\int f(g(x))g'(x)\,dx = \int f(t)\,dt",
     r"\int 2x\cos(x^2)dx = \sin(x^2) + C",
     "замена переменной интегрирование substitution"),
    ("integral-table", "integrals", "school", "theorem.integral_table",
     r"\int \frac{dx}{x} = \ln|x| + C,\quad \int \cos x\,dx = \sin x + C",
     r"\int_1^e \frac{dx}{x} = 1",
     "таблица интегралов integral table"),
    ("fundamental", "integrals", "university", "theorem.fundamental",
     r"\frac{d}{dx}\int_a^x f(t)\,dt = f(x)",
     r"\frac{d}{dx}\int_0^x \sin t\,dt = \sin x",
     "основная теорема анализа fundamental theorem"),
    ("improper", "integrals", "university", "theorem.improper",
     r"\int_a^{\infty} f = \lim_{b \to \infty}\int_a^b f",
     r"\int_1^{\infty} \frac{dx}{x^2} = 1",
     "несобственный интеграл сходимость improper integral"),
    ("area-integral", "integrals", "school", "theorem.area_integral",
     r"S = \int_a^b f(x)\,dx",
     r"\int_0^1 x\,dx = \frac{1}{2}",
     "площадь под графиком интеграл area under curve"),
    ("volume-revolution", "integrals", "university", "theorem.volume_revolution",
     r"V = \pi \int_a^b f^2(x)\,dx",
     r"y=x \text{ на } [0,1]:\; V = \frac{\pi}{3}",
     "объем тела вращения volume of revolution"),
    ("arc-length", "integrals", "university", "theorem.arc_length",
     r"L = \int_a^b \sqrt{1 + (f')^2}\,dx",
     r"y=x \text{ на } [0,1]:\; L = \sqrt2",
     "длина дуги arc length"),
    ("rational-integral", "integrals", "university", "theorem.rational_integral",
     r"\int \frac{P(x)}{Q(x)}dx:\; \text{разложение на простейшие}",
     r"\int \frac{dx}{x^2-1} = \frac{1}{2}\ln\left|\frac{x-1}{x+1}\right|",
     "рациональная дробь простейшие rational fractions"),

    # -------------------------------------------------------------------- series
    ("geometric-series", "series", "university", "theorem.geometric_series",
     r"\sum_{n=0}^{\infty} q^n = \frac{1}{1-q},\quad |q| < 1",
     r"\sum \left(\tfrac{1}{2}\right)^n = 2",
     "геометрический ряд сходимость geometric series"),
    ("harmonic-series", "series", "university", "theorem.harmonic_series",
     r"\sum_{n=1}^{\infty} \frac{1}{n^p} \text{ сходится} \iff p > 1",
     r"p=2:\; \sum \frac{1}{n^2} = \frac{\pi^2}{6}",
     "гармонический ряд p-series сходимость"),
    ("dalembert", "series", "university", "theorem.dalembert",
     r"\lim \left|\frac{a_{n+1}}{a_n}\right| = q < 1 \Rightarrow \text{сходится}",
     r"\sum \frac{1}{n!}:\; q = 0",
     "д'аламбер признак сходимости ratio test"),
    ("cauchy-root", "series", "university", "theorem.cauchy",
     r"\lim \sqrt[n]{|a_n|} = q < 1 \Rightarrow \text{сходится}",
     r"\sum \left(\frac{n}{2n+1}\right)^n:\; q = \frac{1}{2}",
     "коши радикальный признак root test"),
    ("leibniz-series", "series", "university", "theorem.leibniz",
     r"a_n \downarrow 0 \Rightarrow \sum (-1)^n a_n \text{ сходится}",
     r"\sum \frac{(-1)^n}{n} = -\ln 2",
     "лейбниц знакочередующийся ряд alternating series"),
    ("power-series", "series", "university", "theorem.power_series",
     r"R = \lim \left|\frac{a_n}{a_{n+1}}\right|",
     r"\sum \frac{x^n}{n!}:\; R = \infty",
     "степенной ряд радиус сходимости power series radius"),
    ("fourier", "series", "university", "theorem.fourier",
     r"f(x) = \frac{a_0}{2} + \sum (a_n\cos nx + b_n\sin nx)",
     r"\text{пила}: f(x) = x \text{ на } (-\pi;\pi)",
     "фурье ряд разложение fourier series"),
    ("darboux", "series", "university", "theorem.darboux",
     r"f'(x) \text{ не имеет разрывов первого рода}",
     r"\text{производная принимает промежуточные значения}",
     "дарбу производная промежуточные значения darboux"),

    # ------------------------------------------------------------- probability
    ("classical-probability", "probability", "school", "theorem.classical_probability",
     r"P(A) = \frac{m}{n}",
     r"\text{туз из 36 карт}:\; \frac{4}{36} = \frac{1}{9}",
     "классическая вероятность исходы probability classical"),
    ("addition-probability", "probability", "school", "theorem.addition_probability",
     r"P(A \cup B) = P(A) + P(B) - P(A \cap B)",
     r"0{,}5 + 0{,}4 - 0{,}2 = 0{,}7",
     "сложение вероятностей несовместные addition probability"),
    ("multiplication-probability", "probability", "school", "theorem.multiplication_probability",
     r"P(A \cap B) = P(A)\,P(B \mid A)",
     r"0{,}5 \cdot 0{,}6 = 0{,}3",
     "умножение вероятностей независимые multiplication probability"),
    ("conditional-probability", "probability", "school", "theorem.conditional",
     r"P(B \mid A) = \frac{P(A \cap B)}{P(A)}",
     r"P(A)=0{,}5,\; P(AB)=0{,}2 \Rightarrow P(B|A)=0{,}4",
     "условная вероятность conditional probability"),
    ("total-probability", "probability", "university", "theorem.total_probability",
     r"P(A) = \sum_i P(H_i)\,P(A \mid H_i)",
     r"0{,}6\cdot0{,}02 + 0{,}4\cdot0{,}05 = 0{,}032",
     "полная вероятность гипотезы total probability"),
    ("bayes", "probability", "university", "theorem.bayes",
     r"P(H_i \mid A) = \frac{P(H_i)P(A \mid H_i)}{\sum_j P(H_j)P(A \mid H_j)}",
     r"\text{брак от первого завода}:\; 0{,}6",
     "байес формула гипотеза bayes"),
    ("bernoulli", "probability", "school", "theorem.bernoulli",
     r"P_n(k) = \binom{n}{k}p^k(1-p)^{n-k}",
     r"3 броска, 2 орла:\; \frac{3}{8}",
     "бернулли схема испытания binomial bernoulli"),
    ("expectation", "probability", "university", "theorem.expectation",
     r"M[X] = \sum_i x_i p_i,\quad D[X] = M[X^2] - (M[X])^2",
     r"\text{кубик}:\; M = 3{,}5,\; D = \frac{35}{12}",
     "математическое ожидание дисперсия expectation variance"),
    ("variance-properties", "probability", "university", "theorem.variance_properties",
     r"D[aX] = a^2 D[X],\quad D[X+Y] = D[X] + D[Y]",
     r"D[2X] = 4D[X]",
     "свойства дисперсии variance properties"),
    ("normal", "probability", "university", "theorem.normal",
     r"f(x) = \frac{1}{\sigma\sqrt{2\pi}}e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
     r"P(|X-\mu| < \sigma) \approx 0{,}683",
     "нормальное распределение гаусс normal distribution gauss"),
    ("poisson", "probability", "university", "theorem.poisson",
     r"P(k) = \frac{\lambda^k e^{-\lambda}}{k!}",
     r"\lambda = 2:\; P(0) = e^{-2}",
     "пуассон распределение редких событий poisson"),
    ("chebyshev", "probability", "university", "theorem.chebyshev",
     r"P(|X - M[X]| \ge \varepsilon) \le \frac{D[X]}{\varepsilon^2}",
     r"D=1,\; \varepsilon=2:\; P \le 0{,}25",
     "чебышев неравенство chebyshev inequality"),

    # ------------------------------------------------------- complex numbers
    ("complex-form", "complex", "school", "theorem.complex_form",
     r"z = a + bi,\quad |z| = \sqrt{a^2 + b^2}",
     r"z = 3 + 4i:\; |z| = 5",
     "комплексное число действительная мнимая часть complex number"),
    ("complex-conjugate", "complex", "school", "theorem.complex_conjugate",
     r"z \bar{z} = |z|^2",
     r"(3+4i)(3-4i) = 25",
     "сопряженное комплексное conjugate"),
    ("euler-formula", "complex", "university", "theorem.euler_formula",
     r"e^{i\varphi} = \cos\varphi + i\sin\varphi",
     r"e^{i\pi} = -1",
     "эйлер формула экспонента euler formula"),
    ("polar-form", "complex", "university", "theorem.polar_form",
     r"z = r(\cos\varphi + i\sin\varphi) = re^{i\varphi}",
     r"1 + i = \sqrt2\,e^{i\pi/4}",
     "тригонометрическая показательная форма polar exponential"),
    ("demoivre", "complex", "university", "theorem.demoivre",
     r"z^n = r^n(\cos n\varphi + i\sin n\varphi)",
     r"(1+i)^4 = -4",
     "муавра степень формула demoivre power"),
    ("complex-roots", "complex", "university", "theorem.complex_roots",
     r"\sqrt[n]{z} = \sqrt[n]{r}\left(\cos\frac{\varphi + 2\pi k}{n} + i\sin\frac{\varphi + 2\pi k}{n}\right)",
     r"\sqrt[3]{1}:\; 1,\; e^{2\pi i/3},\; e^{4\pi i/3}",
     "корень n-й степени из комплексного числа complex roots"),
    ("complex-multiplication", "complex", "school", "theorem.complex_multiplication",
     r"z_1 z_2 = r_1 r_2\,e^{i(\varphi_1 + \varphi_2)}",
     r"(1+i)(1-i) = 2",
     "умножение комплексных чисел модуль аргумент multiplication"),
    ("quadratic-complex", "complex", "school", "theorem.quadratic_complex",
     r"D < 0:\quad x = \frac{-b \pm i\sqrt{|D|}}{2a}",
     r"x^2+1=0:\; x = \pm i",
     "комплексные корни квадратного уравнения discriminant negative"),
]

ENTRIES: list[dict] = [
    {
        "id": entry_id,
        "area": area,
        "level": level,
        "title": title,
        "latex": latex,
        "example": example,
        "keywords": keywords,
    }
    for entry_id, area, level, title, latex, example, keywords in _RAW
]

BY_ID = {entry["id"]: entry for entry in ENTRIES}


def areas() -> list[str]:
    seen: list[str] = []
    for entry in ENTRIES:
        if entry["area"] not in seen:
            seen.append(entry["area"])
    return seen


def search(query: str = "", area: str = "", level: str = "") -> list[dict]:
    """Plain filter: exact substring over keywords and LaTeX."""
    text = (query or "").strip().lower()
    found = []

    for entry in ENTRIES:
        if area and entry["area"] != area:
            continue
        if level and entry["level"] != level:
            continue
        if text:
            haystack = " ".join(
                [entry["id"], entry["title"], entry["latex"], entry["example"], entry["keywords"]]
            ).lower()
            if text not in haystack:
                continue
        found.append(entry)

    return found


_WORD = re.compile(r"[a-zа-яё]+", re.IGNORECASE)

_STOP = frozenset(
    "как что чем это для или при из на в и с по о об от до не а но же ли "
    "the a an of to in on for with and or is are how what why when "
    "реши решить найди найти помоги нужно надо можно есть был была "
    "такой также еще ещё мне мой "
    # Small talk carries no mathematical signal, but its words are short
    # enough to match inside longer terms: "дела" sits inside "слева", which
    # is how "как дела" ended up returning the one-sided limit theorem.
    "дела дел привет здравствуй спасибо пожалуйста пока ты вы мы я он она "
    "расскажи скажи объясни покажи подскажи дай хочу хотел можешь "
    "hello hi thanks please tell show explain give want".split()
)

# Russian words are inflected; a length-based truncation is unstable because
# "пифагор" (7 letters) and "пифагора" (8) lose different tails and stop
# matching each other. Stripping known endings is stable: both give "пифагор".
_ENDINGS = tuple(sorted(
    """ями ами ыми ими его ого ему ому ых их ая яя ое ее ые ие ый ий ой ей
    ом ем ах ях ам ям ую юю ов ев ии ия ию ья ье ьи ы и а я о е у ю ь""".split(),
    key=len, reverse=True,
))

# The same concept typed in different scripts: a student writes "икс", the
# formula contains "x".
_ALIASES = {
    "икс": "x", "игрек": "y", "зет": "z", "синус": "sin", "косинус": "cos",
    "тангенс": "tan", "котангенс": "cot", "арксинус": "arcsin",
    "арккосинус": "arccos", "арктангенс": "arctan", "логарифм": "log",
    "интеграл": "integral", "производная": "derivative", "предел": "limit",
    "вектор": "vector", "матрица": "matrix",
}


def _stem(word: str) -> str:
    """Strip a Russian ending. Never yields fewer than four characters."""
    word = _ALIASES.get(word, word)
    if len(word) <= 4:
        return word
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def _tokens(text: str) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text or "")]
    return [stem for stem in (_stem(w) for w in words)
            if len(stem) >= 3 and stem not in _STOP]


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, capped at two for speed on long words."""
    if abs(len(a) - len(b)) > 2:
        return 3
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def _fuzzy(stem: str, vocabulary: set[str], limit: int = 2) -> list[str]:
    """Vocabulary stems within a small edit distance of ``stem``.

    Typing "лагранж" for "лагранжа", "пифогор" for "пифагор" or "бином
    нютона" is normal, and an exact-match index answers nothing at all. Two
    edits covers a transposition, a doubled letter and one wrong key without
    turning "куб" into "куб" of something unrelated.
    """
    if len(stem) < 5:
        return []

    # One edit for short words, two for long ones: the longer the word, the
    # safer a wider radius stays.
    radius = 1 if len(stem) <= 6 else 2
    found = [(distance, word) for word in vocabulary
             if (distance := _edit_distance(stem, word)) <= radius]
    found.sort()
    return [word for _distance, word in found[:limit]]


def _vocabulary() -> set[str]:
    """Every stem appearing in any entry's keywords, cached."""
    global _VOCAB
    if _VOCAB is None:
        words: set[str] = set()
        for entry in ENTRIES:
            words.update(_tokens(entry["keywords"]))
        _VOCAB = words
    return _VOCAB


_VOCAB: set[str] | None = None


def _document_frequency() -> dict[str, int]:
    """How many entries mention each stem, cached after the first call."""
    global _DF
    if _DF is None:
        counts: dict[str, int] = {}
        for entry in ENTRIES:
            stems = set(_tokens(entry["keywords"] + " " + entry["title"]))
            for stem in stems:
                counts[stem] = counts.get(stem, 0) + 1
        _DF = counts
    return _DF


_DF: dict[str, int] | None = None


_FORMULA_HINTS: tuple[tuple[str, str], ...] = (
    # A bare expression carries no words to match, so the shape of the formula
    # decides instead: "x^2-5x+6=0" is a quadratic whatever language it is typed in.
    (r"\^\s*2\s*[+\-]", "quadratic"),
    (r"x\s*\^\s*2|\bx2\b|x²", "quadratic"),
    (r"\binteg|\\int|∫", "newton-leibniz"),
    (r"\blim|->|\\to", "first-limit"),
    (r"sin\s*x\s*=", "general-sin"),
    (r"cos\s*x\s*=", "general-cos"),
    (r"tan\s*x\s*=|tg\s*x\s*=", "general-tan"),
    (r"\\sin", "pythagorean-identity"),
    (r"\\cos", "addition-cos"),
    (r"\\tan|\\tg", "general-tan"),
    (r"\blog|\bln\b|\\log|\\ln", "log-rules"),
    (r"\bcomplex|квадратн", "quadratic-complex"),
    (r"\bd/dx|'\b|\bderiv|производн", "derivative-definition"),
    (r"\bdet\b|матриц|matrix", "cramer"),
    (r"\bp\s*\(\s*a\s*\)", "classical-probability"),
)


def _formula_ids(text: str) -> list[str]:
    """Entries implied by the shape of an expression, not by its words."""
    lowered = (text or "").lower()
    found: list[str] = []
    for pattern, entry_id in _FORMULA_HINTS:
        if re.search(pattern, lowered) and entry_id in BY_ID and entry_id not in found:
            found.append(entry_id)
    return found


# Below this a match is noise rather than signal. One exact keyword hit on a
# rare stem scores ~16; a loose one-word coincidence scores under 6.
MIN_SCORE = 6.0

# ------------------------------------------------------------- descriptions
# A student rarely types the theorem's name. "Такая штука, где квадрат
# гипотенузы равен сумме квадратов катетов" is how the question actually
# sounds, and no keyword list will ever enumerate every phrasing.
#
# Each entry below is (phrase, entry id). Matching is case-insensitive over a
# normalised copy of the question, and a phrase scores as strongly as an exact
# keyword: it is not a guess, it is a recognised description.
#
# This list is the cheap first layer. Whatever it misses goes to the model
# classifier, and whatever the classifier is unsure about is asked back.
PHRASES: tuple[tuple[str, str], ...] = (
    # --- Pythagoras and right triangles
    ("квадрат гипотенузы", "pythagoras"),
    ("гипотенузы равен сумме", "pythagoras"),
    ("сумме квадратов катет", "pythagoras"),
    ("два катета", "pythagoras"),
    ("прямоугольн", "pythagoras"),
    ("теорема про треугольник с прямым углом", "pythagoras"),

    # --- Vieta
    ("сумма корней равна", "vieta"),
    ("произведение корней", "vieta"),
    ("корни через коэффициенты", "vieta"),

    # --- quadratic formula
    ("формула корней", "quadratic"),
    ("через дискриминант", "quadratic"),
    ("решить квадратное", "quadratic"),
    ("квадратное уравнение", "quadratic"),

    # --- Bernoulli
    ("вероятность ровно k", "bernoulli"),
    ("схема испытаний", "bernoulli"),
    ("независимых испытаний", "bernoulli"),
    ("ровно k успехов", "bernoulli"),
    ("сколько раз выпадет", "bernoulli"),

    # --- Bayes
    ("пересчитать вероятность", "bayes"),
    ("вероятность гипотезы", "bayes"),
    ("апостериорн", "bayes"),

    # --- limits
    ("синус делить на икс", "first-limit"),
    ("синус икс на икс", "first-limit"),
    ("предел синуса", "first-limit"),
    ("единица плюс один делить", "second-limit"),
    ("число е", "second-limit"),
    ("экспонента в степени", "second-limit"),
    ("обойти неопределенность", "lhopital"),
    ("ноль делить на ноль", "lhopital"),

    # --- derivatives
    ("скорость изменения", "derivative-definition"),
    ("производная сло", "chain-rule"),
    ("функция внутри функции", "chain-rule"),
    ("наклон касательной", "derivative-definition"),

    # --- integrals
    ("площадь под графиком", "area-integral"),
    ("первообразная", "newton-leibniz"),
    ("площадь фигуры ограниченной", "area-integral"),

    # --- geometry
    ("площадь через три стороны", "triangle-area"),
    ("три стороны треугольника", "triangle-area"),
    ("окружность вписана в треугольник", "inradius"),
    ("окружность описана около", "circumradius"),
    ("угол опирается на дугу", "inscribed-angle"),
    ("угол на диаметр", "thales"),

    # --- series
    ("сумма бесконечного ряда", "geometric-series"),
    ("ряд сходится или расходится", "dalembert"),
    ("знакочередующийся", "leibniz-series"),

    # --- trigonometry
    ("синус двойного угла", "double-angle"),
    ("косинус двойного угла", "double-angle"),
    ("перевести сумму в произведение", "sum-to-product"),
    ("как решить тригонометрическое", "general-sin"),

    # --- complex
    ("корень из минус единицы", "complex-form"),
    ("мнимая единица", "complex-form"),

    # --- combinatorics and probability
    ("сколькими способами выбрать", "combinatorics-combinations"),
    ("сколько вариантов переставить", "combinatorics-permutations"),
    ("классическое определение вероятности", "classical-probability"),

    # --- misc
    ("сложный процент", "compound-interest"),
    ("вклад в банке", "compound-interest"),
    ("объем шара", "sphere"),
    ("объем конуса", "cone"),
    ("объем пирамиды", "pyramid"),
)


def _phrase_matches(query: str) -> list[str]:
    """Entry ids whose description appears in the question, best first.

    Longer phrases win: "площадь через три стороны" is a sharper signal than
    "треугольник", so a question containing both is mapped by the longer one.
    """
    text = (query or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)

    found: list[tuple[int, str]] = []
    for phrase, entry_id in PHRASES:
        if entry_id not in BY_ID:
            continue
        if phrase in text:
            found.append((len(phrase), entry_id))

    found.sort(key=lambda pair: -pair[0])

    ordered: list[str] = []
    for _length, entry_id in found:
        if entry_id not in ordered:
            ordered.append(entry_id)
    return ordered




def rank(query: str, limit: int = 4, area: str = "") -> list[dict]:
    r"""Entries most relevant to a free-form question, or nothing at all.

    Returning an empty list is a feature, not a failure. Attaching "one-sided
    limits" to "как дела" is worse than attaching nothing: the reader concludes
    the reference is random and stops trusting it.

    Three rules keep that from happening:

    1. **Exact stems only.** Substring matching was the bug — "дела" is inside
       "слева", so small talk matched a limit theorem. A stem now has to equal
       a keyword or title stem, never merely appear inside one.
    2. **Latex matched by word.** "sin" has to be the word ``\sin``, not three
       letters inside ``\sinh`` or a variable name.
    3. **A score floor and a coverage penalty.** One match in a three-word
       question is weaker than one match in a one-word question, and anything
       under the floor is dropped entirely.
    """
    raw_stems = _tokens(query)

    # A bare expression has no words at all ("реши x^2-5x+6=0" after stop-word
    # removal), so the formula check has to run before the empty check.
    # Otherwise the recognition path was unreachable for exactly the input it
    # was written for.
    implied = _formula_ids(query)

    # A recognised description of the theorem is as good as its name
    described = _phrase_matches(query)
    for entry_id in described:
        if entry_id not in implied:
            implied.append(entry_id)

    if not raw_stems and not implied:
        return []

    if not raw_stems:
        return [BY_ID[entry_id] for entry_id in implied[:limit] if entry_id in BY_ID]

    # Typo tolerance: near matches count, but for less than an exact match.
    # Without the discount "пифогор" would outrank a correctly spelled term.
    vocabulary = _vocabulary()
    stems: list[tuple[str, bool]] = []
    seen: set[str] = set()

    for stem in raw_stems:
        if stem not in seen:
            seen.add(stem)
            stems.append((stem, False))
        for near in _fuzzy(stem, vocabulary):
            if near not in seen:
                seen.add(near)
                stems.append((near, True))

    total = len(ENTRIES) or 1
    frequency = _document_frequency()

    def weight(stem: str) -> float:
        seen_count = frequency.get(stem, 0)
        return math.log((total + 1) / (seen_count + 1)) + 1.0

    scored: list[tuple[float, dict]] = []
    content_words = max(len(raw_stems), 1)

    for entry in ENTRIES:
        if area and entry["area"] != area:
            continue

        keyword_stems = set(_tokens(entry["keywords"]))
        title_stems = set(_tokens(entry["title"]))
        # Whole words from the formula: "sin", "cos", "lim". A substring test
        # here matched variable names.
        latex_words = set(re.findall(r"[a-z]{3,}", entry["latex"].lower()))

        score = 0.0
        matched = 0

        for stem, fuzzy in stems:
            hit = 0.0
            if stem in keyword_stems:
                hit = 3.0
            elif stem in title_stems:
                hit = 2.0
            elif stem in latex_words:
                hit = 1.2
            else:
                continue

            if fuzzy:
                # A typo match is real but weaker than a correct spelling
                hit *= 0.7

            matched += 1
            score += hit * weight(stem)

        if score <= 0:
            continue

        # A question of five words where one matches is mostly about something
        # else. Scaling by coverage keeps such a stray hit from passing.
        coverage = matched / content_words
        score *= 0.45 + 0.55 * min(coverage, 1.0)

        # Two matched words reinforce each other
        score *= 1.0 + 0.35 * (matched - 1)
        scored.append((score, entry))

    scored.sort(key=lambda pair: -pair[0])

    ordered: list[dict] = []
    for entry_id in implied:
        entry = BY_ID[entry_id]
        if area and entry["area"] != area:
            continue
        ordered.append(entry)

    for score, entry in scored:
        if len(ordered) >= limit:
            break
        if entry not in ordered:
            # The floor applies to everything except a recognised formula
            # shape, which is an explicit signal rather than a lucky word.
            if score < MIN_SCORE and len(ordered) >= 0:
                break
            ordered.append(entry)

    return ordered[:limit]


def as_prompt_context(entries: list[dict], translate: dict[str, str] | None = None) -> str:
    """Format entries as plain text for injection into the model's prompt.

    ``translate`` maps a title key to its rendered name, so the model sees
    "Теорема Виета" instead of "theorem.vieta".
    """
    if not entries:
        return ""

    lines = []
    for entry in entries:
        name = (translate or {}).get(entry["title"], entry["title"])
        lines.append(f"- {name}: {entry['latex']}")
        if entry["example"]:
            lines.append(f"  example: {entry['example']}")
    return "\n".join(lines)


__all__ = ["ENTRIES", "BY_ID", "areas", "search", "rank", "as_prompt_context"]
