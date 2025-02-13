#!/bin/bash

#  Diese Script erstellt ein A4 PDF
#  Ein A4 Blatt ergibt 4 Badge-Streifen.
#  Badge-Streifen = 2x A7 querformat zum zusammenklappen,
#  so das aussen das sichtbare Namensschild und innen ggf.nötige Zusatzinfos stehen
# 
#  1 PDF mit den A4 Vorderseiten (namensschilder_sichtbar.tex -> namensschilder_sichtbar.pdf)
#  2 PDF mit den A4 Innenseiten (namensschilder_innenseite.tex -> namensschilder_innenseite.pdf)
#  und fügt deren seiten abwechselnd zuammen zum namensschilder2024.pdf,
#  wo jede zweite 2 die Innenseite eines Badges darstellt
#  CSV = die *.csv datei mit den nötigen Angaben für Aussen- und Innenseite
# set CSV=bin/badges.empty.csv

export BADGE_CSV=csv/badges2025_hackaton.csv # the input CSV
export BADGE_PDF=csv/badges2025_conf.pdf # the final PDF
echo "CREATING BADGES for CSV: BADGECSV"
#echo "Converting JSON to CSV"
# python3 bin/convert2025.py

echo "Sanitize $BADGE_CSV"
sed -i 's/\"//g' $BADGE_CSV

echo "writing inner site of badges"
pdflatex "\newcommand{\BadgeCSV}{$BADGE_CSV} \input{tex/namensschilder_innen.tex}"
echo "writing visible site of badges"
pdflatex "\newcommand{\BadgeCSV}{$BADGE_CSV} \input{tex/namensschilder_sichtbar.tex}"
# echo "combine in- and outside"
# pdflatex

# pdflatex "\newcommand{\PDFSichtbar}{namensschilder_sichtbar.pdf} \newcommand{\PDFInnen}{namensschilder_innenseite.pdf} \input{namensschilder2023.tex}"
#pdflatex namensschilder2024_innen.tex

#echo "writing outside of badges"
#pdflatex namensschilder2024_sichtbar.tex

#echo "combining in- and outside"
#pdflatex namensschilder2024.tex
# qpdf --empty --collate=1 --pages namensschilder2024_sichtbar.pdf namensschilder2024_innen.pdf -- out.pdf