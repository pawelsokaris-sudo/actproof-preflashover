# Lessons Learned — actproof-preflashover v1.4

Notatki dla siebie samego za 6+ miesięcy, gdy wrócę do podobnych eksperymentów.

## A. Cztery ADDENDUM-y pre-data (proceduralne)

1. **Test convention against live data**, nie tylko syntactic check. 
   Trzy z czterech ADDENDUM-ów (001 bot filter, 003 User-Agent, 004 Stockfish 
   timeout) wynikały z deficytu testowania operacyjnego — kod kompilował się, 
   ale nie był sprawdzony przeciwko realnemu środowisku.

2. **Dataset survey przed preregistracją.** ADDENDUM-002 wymagał zmiany 
   Source z Lichess Elite na TWIC, bo Lichess Elite miał 0 partii spełniających 
   frozen criteria. To wymagało zmiany preregistracji. Wcześniej survey 
   datasetu (sprawdzić ile partii faktycznie istnieje) zapobiegłby tej iteracji.

3. **Per-position timeout dla deterministycznych engines.** ADDENDUM-004 
   wynikał z założenia "no time limit" w preregistracji — patologiczne pozycje 
   mogą wymagać godzin compute przy depth=22. Każda przyszła preregistracja 
   musi explicit zdefiniować timeout per-position dla każdej zewnętrznej 
   analizy (Stockfish, KataGo, etc.).

## B. Methodological gap (pojawił się dopiero w secondary controls)

4. **Permutation baseline musi kontrolować bias sensora, nie tylko bias danych.**
   Preregistrowany baseline w v1.4 (pseudo-FO uniform z [0, n_plies)) testował 
   hipotezę słabszą niż zamierzona. Stratified baseline (z empirycznej 
   dystrybucji FO_ply) byłby właściwy. Wykryto dopiero post-hoc.

## C. Mandatory sanity controls przed zamrożeniem preregistracji (propozycja, oparta na review GPT):

Przed zamrożeniem preregistracji każdego przyszłego eksperymentu ActProof:

1. **Distribution check sygnału w czasie.** Uruchom sensor na pilot dataset, 
   sprawdź rozkład czasowy peaks. Jeśli >70% sygnału w jednym buckecie 
   (debiut, endgame) — strukturalny bias do uwzględnienia w baseline.

2. **Component dominance test.** Rozłóż sygnał na komponenty (per figura, 
   per square, per channel). Jeśli jedna cecha dominuje >70% — uzasadnij 
   teoretycznie lub przeskaluj.
   *Lesson z v1.4: król masa=100 dał 98% pole. Mass scaling wymagał review.*

3. **Random/null data control.** Uruchom sensor na losowych danych z tej 
   samej domeny (random games, random sequences). Jeśli sensor reaguje 
   tak samo na sensowne i bezsensowne dane — sensor mierzy strukturę 
   formatu, nie zawartość.

4. **Baseline-sensor bias coupling.** Sprawdź czy zaproponowany permutation 
   baseline ma tę samą strukturę temporal/spatial co sygnał sensora. 
   Jeśli sensor ma bias do określonej fazy, baseline uniform tego nie 
   kontroluje.

## D. Konstrukcyjne lekcje dla operacjonalizacji fizycznej

5. **Wartość domenowa ≠ waga fizyczna.** Król ma "nieskończoną" wartość 
   strategiczną w szachach, ale dawanie mu masy 100 w polu fizycznym 
   sprawia że sensor mierzy tylko króla. Wartości szachowe (P:1, Q:9 etc.) 
   były zaprojektowane do trade analysis, nie do modeli pola.

6. **Decay function determinuje skalę.** `1/r` daje globalną dominację 
   dużych mas. Lokalne kernels (`1/r²`, gaussian, finite cutoff) 
   umożliwiają mierzenie figur o niskiej masie.

7. **Peak selection determinuje fazę.** `find_peaks` z `prominence=0.8` 
   wybiera pierwszy główny gradient = debiut. Alternatywy: ostatni peak 
   przed markerem, pik nietypowy względem fazy, sekwencja peaków.

## E. Honest reporting principle

8. **Pozytywny mechaniczny wynik ≠ pozytywna interpretacja.** Preregistrowana 
   decision matrix może dać PASS, ale strukturalny confound w designie może 
   uczynić tę interpretację bezwartościową. Secondary controls po werdykcie 
   są **konieczne**, nie opcjonalne.

9. **Multi-model peer review działa.** Cztery niezależne modele AI (Claude, 
   GPT, Antigravity, Grok) konwergujące na tej samej diagnozie wzmacniają 
   robustność wniosku. Pojedynczy model może mieć blind spot (Claude w 
   tej rozmowie trzykrotnie błędnie przypisał motywację autora).

10. **Negatywny wynik z czystym paper trail > pozytywny wynik z naciąganiem.** 
    Komuś za rok wracającemu do tematu, jednoznaczna falsyfikacja v1.2 
    operacjonalizacji jest mocniejszą podstawą niż "subtelny, wymagający 
    dalszego badania sygnał".
