import requests
import json

def analyze_text(text, api_key):
    """
    Analyze text using Perspective API
    Returns scores for toxicity, insults, and threats
    """
    url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={api_key}"
    
    data = {
        'comment': {'text': text},
        'languages': ['en'],
        'requestedAttributes': {
            'TOXICITY': {},
            'SEVERE_TOXICITY': {},
            'IDENTITY_ATTACK': {},
            'INSULT': {},
            'PROFANITY': {},
            'THREAT': {},
            'SEXUALLY_EXPLICIT': {},
            'FLIRTATION': {}
        }
    }
    
    try:
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data)
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract scores
        scores = {}
        attributes = ['TOXICITY', 'SEVERE_TOXICITY', 'IDENTITY_ATTACK', 
                      'INSULT', 'PROFANITY', 'THREAT', 
                      'SEXUALLY_EXPLICIT', 'FLIRTATION']
        
        for attr in attributes:
            scores[attr] = result['attributeScores'][attr]['summaryScore']['value']
        
        return scores
    
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


def main(message):
    # Get API key
    api_key = "AIzaSyAHWkeW3GuYixc247rFNOxvMPaESt6DbVg"

    # Get user input
    text = message

    result = analyze_text(text, api_key)
    
    # Display results
    parsed = f'''
  TOXICITY:          {result['TOXICITY']:.2%}")
  SEVERE_TOXICITY:   {result['SEVERE_TOXICITY']:.2%}")
  IDENTITY_ATTACK:   {result['IDENTITY_ATTACK']:.2%}")
  INSULT:            {result['INSULT']:.2%}")
  PROFANITY:         {result['PROFANITY']:.2%}")
  THREAT:            {result['THREAT']:.2%}")
  SEXUALLY_EXPLICIT: {result['SEXUALLY_EXPLICIT']:.2%}")
  FLIRTATION:        {result['FLIRTATION']:.2%}")'''
    return [result, parsed]
