from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

DATA = [
("software engineer established company technical interview salary based on experience",0),
("data analyst qualifications benefits office location normal recruitment process",0),
("backend developer interview required company website recruiter email",0),
("marketing manager experience required normal application responsibilities",0),
("pay registration fee guaranteed income no interview instant joining",1),
("urgent hiring earn money quickly send bank details processing fee",1),
("work from home easy money no experience pay security deposit",1),
("send money for training guaranteed job immediately",1),
]
X=[x for x,y in DATA]; y=[y for x,y in DATA]
model=Pipeline([("tfidf",TfidfVectorizer(ngram_range=(1,2))),("clf",LogisticRegression(max_iter=1000))])
model.fit(X,y)
pred=model.predict(X)
print(classification_report(y,pred,target_names=["legitimate","fraudulent"]))
print(confusion_matrix(y,pred))
out=Path(__file__).resolve().parent.parent/"backend"/"app"/"model.joblib"
joblib.dump(model,out)
print("Saved:",out)
