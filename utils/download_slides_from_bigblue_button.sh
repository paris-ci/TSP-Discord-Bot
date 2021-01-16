#!/usr/bin/env bash
URL=$@
DIR=$(mktemp -d)

CHAR=1
while [[ $CHAR -le 500 ]]
do
   file=${DIR}/$(printf "%03d" "$CHAR")
   svg_file=${file}.svg
   png_file=${file}.png
   pdf_file=${file}.pdf


   wget -q "$URL$CHAR" -O ${svg_file}
   if [[ $? -ne 0 ]]
    then
        rm ${svg_file}
        break
   fi

   inkscape ${svg_file} --export-pdf=${pdf_file} > /dev/null 2>&1

   #cairosvg "${svg_file}" -o "${png_file}"
   rm ${svg_file}
   CHAR=$(( $CHAR + 1 ))
done

#convert ${DIR}/*.png ${DIR}/output.pdf
#zip -qj ${DIR}/output.zip ${DIR}/*.svg

pdfjoin ${DIR}/*.pdf -o ${DIR}/output.pdf

#rm ${DIR}/*.png
##convert ${DIR}/*.svg ${DIR}/output.pdf
echo ${DIR}/output.pdf
