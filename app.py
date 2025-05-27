# app.py
import flask
import joblib
import pandas as pd
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Load Model and Feature Names ---
try:
    model = joblib.load('best_xgboost_model_sampled.joblib')
    logging.info("Model loaded successfully.")
except FileNotFoundError:
    logging.error("Model file 'best_xgboost_model_sampled.joblib' not found.")
    model = None
except Exception as e:
    logging.error(f"Error loading model: {e}")
    model = None

try:
    expected_features = joblib.load('encoded_feature_names.joblib')
    logging.info("Feature names loaded successfully.")
    logging.debug(f"Expected features: {expected_features}")
except FileNotFoundError:
    logging.error("Feature names file 'encoded_feature_names.joblib' not found.")
    expected_features = None
except Exception as e:
    logging.error(f"Error loading feature names: {e}")
    expected_features = None

# Initialize Flask app
app = flask.Flask(__name__)

# --- Define Routes ---

# Route for the main page (serving the HTML form)
@app.route('/')
def home():
    # Simple check if model/features loaded
    if model is None or expected_features is None:
         return "Error: Model or feature names failed to load. Check server logs.", 500
    return flask.render_template('index.html') # Assumes index.html is in a 'templates' folder

# Route for handling prediction requests
@app.route('/predict', methods=['POST'])
def predict():
    if model is None or expected_features is None:
        return flask.jsonify({'error': 'Model or feature names not loaded'}), 500

    try:
        # Get data from the POST request
        data = flask.request.get_json(force=True)
        logging.info(f"Received data: {data}")

        # --- Preprocessing and Feature Engineering ---
        # Convert input data to DataFrame
        input_df = pd.DataFrame([data])

        # Basic type conversions and validation
        input_df['Size'] = pd.to_numeric(input_df['Size'], errors='coerce')
        input_df['Rooms'] = pd.to_numeric(input_df['Rooms'], errors='coerce').astype(int)
        input_df['Year'] = pd.to_numeric(input_df['Year'], errors='coerce').astype(int)
        input_df['Apt_Floor'] = pd.to_numeric(input_df['Apt_Floor'], errors='coerce').astype(int)
        input_df['Total_Floors'] = pd.to_numeric(input_df['Total_Floors'], errors='coerce').astype(int)

        # Ensure Total_Floors >= Apt_Floor and >= 1
        input_df['Total_Floors'] = input_df.apply(lambda row: max(row['Apt_Floor'], row['Total_Floors'], 1), axis=1)
        # Ensure Rooms >= 1
        input_df['Rooms'] = input_df['Rooms'].replace(0, 1)

        # Feature Engineering (must match training)
        input_df['Building Age'] = 2025 - input_df['Year'] # Use the same reference year as training
        input_df['Is_First_Floor'] = (input_df['Apt_Floor'] == 1).astype(int)
        input_df['Is_Top_Floor'] = (input_df['Apt_Floor'] == input_df['Total_Floors']).astype(int)
        # Add other engineered features if you used them (Floor_Ratio, Avg_Room_Size, Sq terms etc.)
        # Make sure to handle potential division by zero as done during training
        input_df['Floor_Ratio'] = input_df['Apt_Floor'] / input_df['Total_Floors']
        input_df['Avg_Room_Size'] = input_df['Size'] / input_df['Rooms']
        input_df['Building Age Sq'] = input_df['Building Age']**2
        input_df['Size Sq'] = input_df['Size']**2


        # One-Hot Encode 'Area' - crucial step
        # Ensure 'Area' column exists and is treated as category for encoding
        input_df['Area'] = input_df['Area'].astype('category')
        input_encoded = pd.get_dummies(input_df, columns=['Area'], drop_first=False)

        # Align columns with the features the model was trained on
        # This adds missing columns (with value 0) and removes extra ones
        input_aligned = input_encoded.reindex(columns=expected_features, fill_value=0)
        logging.info(f"Shape after alignment: {input_aligned.shape}")
        logging.debug(f"Columns after alignment: {input_aligned.columns.tolist()}")

        # Select only the expected features in the correct order
        final_input = input_aligned[expected_features] # Ensure order matches

        # --- Prediction ---
        prediction_log = model.predict(final_input)

        # Inverse transform the prediction
        prediction_numpy = np.expm1(prediction_log[0]) # Get the single prediction value (might be float32/64)
        prediction_numpy = max(0, prediction_numpy) # Ensure non-negative

        # converting numpy float to py
        prediction_python = float(round(prediction_numpy, 2))

        logging.info(f"Log prediction: {prediction_log[0]}, Final prediction: {prediction_python}")

        # return prediction json
        return flask.jsonify({'prediction': prediction_python}) # Pass the Python float

    except KeyError as e:
        logging.error(f"Missing key in input data: {e}")
        return flask.jsonify({'error': f'Missing input field: {e}'}), 400
    except ValueError as e:
        logging.error(f"Value error during processing: {e}")
        return flask.jsonify({'error': f'Invalid input value: {e}'}), 400
    except Exception as e:
        logging.error(f"Prediction error: {e}", exc_info=True) # Log full traceback
        return flask.jsonify({'error': 'An error occurred during prediction.'}), 500


#run
if __name__ == '__main__':

    app.run(debug=False)
