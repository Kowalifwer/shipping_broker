import spacy

# Load spaCy model (download with: python -m spacy download en_core_web_md)
nlp = spacy.load('en_core_web_md')

s1 = """<html><body><div>
<div>
<h2>Pleased to have your firm orders for our home tonnages</h2>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<div>
<div>
<div>
<p>&nbsp;</p>
<div>
<div>
<p><b>IVY 1&nbsp;</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;3000 dwcc&nbsp;&nbsp;&nbsp;&nbsp;138.700 cbft&nbsp;&nbsp;&nbsp;&nbsp;’85 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;03rd Febr&nbsp;<b>@ Hereke</b>&nbsp;</p>
<p>&nbsp;</p>
<p><b>SALIX</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;3300 dwcc&nbsp;&nbsp;&nbsp;&nbsp;138.700 cbft&nbsp;&nbsp;&nbsp;&nbsp;’86 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;12th Febr&nbsp;<b>@ &nbsp;Malta</b></p>
<p>&nbsp;</p>
<div></div></div>
<div></div></div>
<div></div></div>
<p><b>UTA</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 3350 dwcc&nbsp;&nbsp;&nbsp;&nbsp;140.375 cbft&nbsp;&nbsp;&nbsp;&nbsp;’84 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;20th Feb&nbsp;<b>@</b>&nbsp;&nbsp;<b>Marmara</b></p></div>
<div>&nbsp;</div></div>
<p>&nbsp;</p>
<p>Please add our &nbsp;e-mail&nbsp;<a href="mailto:brokers@verdashipping.com">brokers@verdashipping.com</a>&nbsp;to your circulation list.</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>Best Regards</p>
<p>VERDA SHIPPING LTD</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>Saadet TEKIR &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;&nbsp;</p>
<p>Skype: saadettekir &nbsp;</p>
<p>&nbsp;</p>
<p>Ozan AKTAS</p>
<p>Skype: ozanaktaswakes</p><br>
<img data-imagetype="External" src="http://bulten.verdashipping.com/s/dtaik/circular@unimarservice.ltd"> </div></div>
</body></html>"""

s2 = """<html><body><div>
<div>
<h2>Pleased to have your firm orders for our home tonnages</h2>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<div>
<div>
<div>
<p>&nbsp;</p>
<div>
<div>
<p><b>SALIX</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;3300 dwcc&nbsp;&nbsp;&nbsp;&nbsp;138.700 cbft&nbsp;&nbsp;&nbsp;&nbsp;’86 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;&nbsp;<strong>SPOT</strong>&nbsp;<b>@ &nbsp;Abu Qir</b></p>
<p>&nbsp;</p>
<p><b>IVY 1&nbsp;</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;3000 dwcc&nbsp;&nbsp;&nbsp;&nbsp;138.700 cbft&nbsp;&nbsp;&nbsp;&nbsp;’85 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;<strong>&nbsp;SPOT</strong>&nbsp;<b>@ Izmit</b>&nbsp;</p>
<p>&nbsp;</p>
<div></div></div>
<div></div></div>
<div></div></div>
<p><b>UTA</b>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 3350 dwcc&nbsp;&nbsp;&nbsp;&nbsp;140.375 cbft&nbsp;&nbsp;&nbsp;&nbsp;’84 blt &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;20th Feb&nbsp;<b>@</b>&nbsp;&nbsp;<b>Marmara</b></p></div>
<div>&nbsp;</div></div>
<p>&nbsp;</p>
<p>Please add our &nbsp;e-mail&nbsp;<a href="mailto:brokers@verdashipping.com">brokers@verdashipping.com</a>&nbsp;to your circulation list.</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>Best Regards</p>
<p>VERDA SHIPPING LTD</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>Saadet TEKIR &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;&nbsp;</p>
<p>Skype: saadettekir &nbsp;</p>
<p>&nbsp;</p>
<p>Ozan AKTAS</p>
<p>Skype: ozanaktaswakes</p><br>
<img data-imagetype="External" src="http://bulten.verdashipping.com/s/zghso/circular@unimarservice.ltd"> </div></div>
</body></html>"""

import time

start = time.time()

# Tokenize and preprocess the documents
doc1 = nlp(s1)
doc2 = nlp(s2)

print(doc1)

# Calculate Word Mover's Distance
for i in range(10):
    wmd_distance = doc1.similarity(doc2)
    print(f"Word Mover's Distance: {wmd_distance}")

end = time.time()

print(f"Time taken: {end - start} seconds")