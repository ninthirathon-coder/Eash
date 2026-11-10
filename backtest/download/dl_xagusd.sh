get() { # $1=path-suffix $2=date $3=datemonth $4=out
  U="https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/xagusd/$1"
  curl -sS -m 60 -c cj_ag.txt -b cj_ag.txt "$U" -o p_ag.html
  TK=$(grep -oE 'name="tk" id="tk" value="[^"]*"' p_ag.html | head -1 | sed 's/.*value="//;s/"//')
  curl -sS -m 300 -b cj_ag.txt -c cj_ag.txt -e "$U" -X POST https://www.histdata.com/get.php \
    -d "tk=$TK&date=$2&datemonth=$3&platform=ASCII&timeframe=M1&fxpair=XAGUSD" -o "d_xagusd/raw/$4.zip"
  echo -n "$4:$(stat -c%s d_xagusd/raw/$4.zip) "
}
mkdir -p d_xagusd/raw d_xagusd/csv
for y in $(seq 2009 2025); do get $y $y $y $y; sleep 2; done
for m in $(seq 1 11); do get 2026/$m 2026 2026$(printf %02d $m) 2026$(printf %02d $m); sleep 2; done
for z in d_xagusd/raw/*.zip; do unzip -oq $z -d d_xagusd/csv/; done
