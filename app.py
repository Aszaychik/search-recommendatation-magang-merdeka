from flask import Flask, request, redirect, jsonify, render_template
from flask_assets import Bundle, Environment
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ast
from flask import url_for

app = Flask(__name__)

assets = Environment(app)
css = Bundle("src/main.css", output="dist/main.css")

assets.register("css", css)
css.build()

magang_opportunities = pd.read_csv('data/magang_opportunities.csv')
cleaned_data = pd.read_csv('data/cleaned_data.csv')

tfidf_vectorizer = TfidfVectorizer()

X = tfidf_vectorizer.fit_transform(cleaned_data['result_preprocessing'])

def random_magang(n=10):
    filter_magang = magang_opportunities.dropna(subset=['mitra_name', 'logo'])
    items = filter_magang.sample(n)
    return items.to_dict('records')

# Processes the skills column to extract the skill names
def skills_processing(skills):
    try:
        skills_list = ast.literal_eval(skills)
        if isinstance(skills_list, list):
            return [skill['name'] for skill in skills_list]
        else:
            return skills_list  # Return as is if not a list
    except (ValueError, SyntaxError):
        return skills  # Return original value if parsing fails


def content_based_recommendation(content_id, n=10):
    content_index = magang_opportunities.index[magang_opportunities['id'] == content_id].tolist()[0]

    similarity_score = cosine_similarity(X)
    sorted_similar_content = similarity_score[content_index].argsort()[::-1]

    top_n_content = sorted_similar_content[1:n+1]

    recommendation_result = pd.DataFrame(columns=['id', 'name', 'mitra', 'score'])

    for i in top_n_content:
        score = similarity_score[content_index][i]
        if score != 0: # Check if similarity score is not equal to 0
            recommendation_result = pd.concat([
                recommendation_result,
                pd.DataFrame({
                    'id': [magang_opportunities.iloc[i]['id']],
                    'name': [magang_opportunities.iloc[i]['name']],
                    'mitra': [magang_opportunities.iloc[i]['mitra_name']],
                    'score': [score]
                })
            ], ignore_index=True)

    return recommendation_result


def query_based_recommendation(query):
    query = query.casefold()  # Make sure the query is in lowercase
    query_vector = tfidf_vectorizer.transform([query])
    
    similarity_score = cosine_similarity(query_vector, X)
    sorted_similar_content = similarity_score.argsort()[0][::-1]
    top_n_content = sorted_similar_content[0:]

    recommendation_result = pd.DataFrame(columns=['id', 'name', 'mitra', 'score'])

    for i in top_n_content:
        score = similarity_score[0][i]
        if score != 0:  # Check if similarity score is not equal to 0
            recommendation_result = pd.concat([
                recommendation_result,
                pd.DataFrame({
                    'id': [magang_opportunities.iloc[i]['id']],
                    'name': [magang_opportunities.iloc[i]['name']],
                    'mitra': [magang_opportunities.iloc[i]['mitra_name']],
                    'score': [score]
                })
            ], ignore_index=True)

    return recommendation_result

@app.route('/')
def home():
    items = random_magang(3)
    return render_template('index.html', items=items)

@app.route('/magang')
def magang_list():
    query = request.args.get('query')
    items = magang_opportunities.to_dict('records')

    if query:
        items = [item for item in items if query.lower() in item['name'].lower() or query.lower() in item['mitra_name'].lower()]

    return render_template('magang_list.html', items=items)

@app.route('/recommend', methods=['GET'])
def recommend_page():
    query = request.args.get('query')
    if query:
        query_based_recommend_result = query_based_recommendation(query)
        recommend_ids = query_based_recommend_result['id']
        recommend_scores = query_based_recommend_result['score']

        recommend_items = []
        for rec_id, score in zip(recommend_ids, recommend_scores):
            rec_item = magang_opportunities[magang_opportunities['id'] == rec_id].to_dict('records')[0]
            rec_item['score'] = score
            recommend_items.append(rec_item)

        return render_template('query_recommend.html', recommend_items=recommend_items, query=query)
    return render_template('recommend_page.html')

@app.route('/content-based-recommend/<content_id>', methods=['GET'])
def content_based_recommend(content_id):
    n = request.args.get('n', 5, type=int)
    result = content_based_recommendation(content_id, n)
    print(result)
    return jsonify(result.to_dict(orient='records'))

@app.route('/query-based-recommend', methods=['GET'])
def query_based_recommend():
    query = request.args.get('query')
    result = query_based_recommendation(query)
    return jsonify(result.to_dict(orient='records'))

@app.route('/magang/<content_id>', methods=['GET'])
def magang_detail(content_id):
    item = magang_opportunities[magang_opportunities['id'] == content_id].to_dict('records')[0]
    skills = skills_processing(item['detail_skills'])

    recommend_result = content_based_recommendation(content_id, 6)
    recommend_ids = recommend_result['id']
    recommend_scores = recommend_result['score']

    recommend_items = []
    for rec_id, score in zip(recommend_ids, recommend_scores):
        rec_item = magang_opportunities[magang_opportunities['id'] == rec_id].to_dict('records')[0]
        rec_item['score'] = score
        recommend_items.append(rec_item)

    # Render the template with the recommended items in the specified order
    return render_template('magang_detail.html', item=item, recommend_items=recommend_items, skills=skills)

if __name__ == '__main__':
    app.run()