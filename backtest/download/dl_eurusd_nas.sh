get() { # $1=pair $2=year outdir
  U="https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/$1/$2"
  curl -sS -m 60 -c cj_$1.txt -b cj_$1.txt "$U" -o p_$1.html
  TK=$(grep -oE 'name="tk" id="tk" value="[^"]*"' p_$1.html | head -1 | sed 's/.*value="//;s/"//')
  P=$(echo $1 | tr a-z A-Z)
  curl -sS -m 300 -b cj_$1.txt -c cj_$1.txt -e "$U" -X POST https://www.histdata.com/get.php \
    -d "tk=$TK&date=$2&datemonth=$2&platform=ASCII&timeframe=M1&fxpair=$P" -o "$3/raw/$2.zip"
  echo "$1 $2 $(stat -c%s $3/raw/$2.zip)"
}
for p in eurusd nsxusd; do
  mkdir -p d_$p/raw d_$p/csv
  for y in $(seq 2010 2025); do get $p $y d_$p; sleep 2; done
  for z in d_$p/raw/*.zip; do unzip -oq $z -d d_$p/csv/; done
done
