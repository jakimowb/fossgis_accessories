FROM ubuntu:24.10
LABEL Name=fossgis-namensschilder Version=0.0.2
RUN apt update && apt install -y \
    pandoc texlive texlive-fonts-extra texlive-bibtex-extra \
    texlive-latex-base texlive-latex-extra texlive-font-utils \
    texlive-lang-german locales curl && \
    apt clean && \  
    rm -rf /var/lib/apt/lists/*

RUN sed -i -e 's/# de_DE.UTF-8 UTF-8/de_DE.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=de_DE.UTF-8
ENV LANGUAGE=de_DE.UTF-8 LANG=de_DE.UTF-8 LC_ALL=de_DE.UTF-8
WORKDIR /home/ubuntu
