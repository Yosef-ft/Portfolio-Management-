import sys
import os
import time

import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf
import sidetable as stb
import mplfinance as mpf
from scipy.stats import zscore

from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.graphics.tsaplots import plot_pacf
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.tsa.stattools import adfuller

from sklearn.metrics import mean_absolute_error, mean_squared_error

from tensorflow.keras.losses import MeanSquaredError
from tensorflow.keras.metrics import MeanSquaredError, RootMeanSquaredError, MeanAbsoluteError
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import InputLayer, LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping 
from tensorflow.keras.metrics import Accuracy, Precision, F1Score, Recall
from tensorflow.keras.losses import BinaryCrossentropy
from tensorflow.keras.optimizers import Adam
import tensorflow as tf

import pmdarima as pm
import ta

from logger import LOGGER
logger = LOGGER


class ModelUtil:

    def __init__(self):
        self.logger = logger
    
    def train_test_split(self, data, test_size, model_name):
        '''
        This funciont is used to split the data to training and testing based on number of dates

        Parameter:
        ----------
            data(pd.DataFrame)
            test_size(int): number of days to consider for testing

        Return:
        ------
            train_data, test_data
        '''

        if model_name == 'SARIMAX' or 'LSTM':
            series = data[['Close', 'ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband',
                'Mband', 'ketler']]
            
        else:
            series = pd.DataFrame(data['Close'])

        train = pd.DataFrame(series[:-test_size])
        test = pd.DataFrame(series[-test_size:])

        train_dates = data.index[:-test_size]
        test_dates = data.index[-test_size:]   

        return train, test, train_dates, test_dates, series
    
    
    def train_Arima_model(self,data, test_size=60, model_name = "ARIMA" ,exogenous=False):

        train, test, train_dates, test_dates, series = self.train_test_split(data, test_size, model_name)
        
        self.logger.info(f"Training {model_name} started ....")
        start_time = time.time()
        
        if model_name == 'ARIMA':
            model = pm.auto_arima(train['Close'], seasonal=False, trace=True, error_action='ignore',
                                    suppress_warnings=True, stepwise=True)
        else:
            model = pm.auto_arima(train['Close'].values, X= train[['ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband',
                        'Mband', 'ketler']].values if model_name =="SARIMAX" else None,
                                    start_P=0,
                                    start_q = 0,
                                    max_p=1, max_q=1, max_d=1, start_p=0, 
                                    seasonal=False if model_name=="ARIMA" else True, m=12, trace=True,
                                    error_action='ignore', suppress_warnings=True
                                )
        
        end_time = time.time()
        self.logger.info(f"Training {model_name} took {round(end_time - start_time, 2)} seconds")

        return model    
    

    def plot_model_forecast(self, model,data,model_name, test_size):
        '''
        This function is used to plot the model forecast with intervals

        Parameter:
        ---------
            model: the trained model
            data(pd.DataFrame): the data
            model_name: the name of the model - ARIMA, SARIMA, SARIMAX
            test_size: the size of days for testing


        Return:
        -------
            matplotlib.pyplot 
        '''
        train, test, train_dates, test_dates, series = self.train_test_split(data, test_size, model_name)
        forecast = model.predict(n_periods=test_size, X=test[['ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values if model_name == 'SARIMAX' else None)

        # # Get the confidence intervals as well
        forecast_conf, conf_int = model.predict(n_periods=test_size, X=test[['ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values if model_name == 'SARIMAX' else None, return_conf_int=True)

        fig, (ax1, ax2) = plt.subplots(2,1, figsize=(15,12))

        ax1.plot(train_dates[-90:], series[-test_size -90: -test_size]['Close'], label = 'Training data', color='blue')
        ax1.plot(test_dates, test['Close'],label='Actual', color = 'green')
        ax1.plot(test_dates, forecast, label='Forecast', color='red')

        ax1.fill_between(test_dates,
                            conf_int[:, 0],
                            conf_int[:, 1],
                            color='red',
                            alpha=0.1
                            )

        ax1.set_title('Price frocast with confidence interval')
        ax1.legend()
        ax1.grid(True)

        if model_name == 'ARIMA':
            errors = test['Close'].values - forecast.values
        else:
            errors = test['Close'] - forecast
        ax2.plot(test_dates, errors, color='red', label='Forecast Errors')
        ax2.axhline(y=0, color='black', linestyle='--')
        ax2.fill_between(test_dates, errors, np.zeros_like(errors),
                            alpha=0.5, color='red' if np.mean(errors) < 0 else 'green')

        ax2.set_title("Forecast errors (actual - forecast)")
        ax2.legend()
        ax2.grid()

        plt.tight_layout()
        plt.show()


    def model_metrics(self, model, model_name,data, test_size):
        
        train, test, train_dates, test_dates, series = self.train_test_split(data, test_size, model_name)

        forecast = model.predict(n_periods=test_size, X=test[['ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values if model_name=='SARIMAX' else None)

        # # Get the confidence intervals as well
        forecast_conf, conf_int = model.predict(n_periods=test_size, X=test[['ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values if model_name == 'SARIMAX' else None, return_conf_int=True)
        actual_values = test['Close'].values

        # Mean Absolute Error (MAE)
        mae = mean_absolute_error(actual_values, forecast)

        # Root Mean Squared Error (RMSE)
        rmse = np.sqrt(mean_squared_error(actual_values, forecast))

        # Mean Absolute Percentage Error (MAPE)
        mape = np.mean(np.abs((actual_values - forecast) / actual_values)) * 100

        # Print the results
        print(f"Mean Absolute Error (MAE): {mae}")
        print(f"Root Mean Squared Error (RMSE): {rmse}")
        print(f"Mean Absolute Percentage Error (MAPE): {mape}%")


    def create_sequence(self, data, time_steps =60):
        X, y = [], []
        for i in range(len(data) - time_steps):
            X.append(data[i:(i + time_steps)])
            y.append(data[i + time_steps])
        return np.array(X), np.array(y)

    def train_lstm(self, data, seq_length=60, epochs=10, batch_size=32 ,model_name='LSTM'):
        column = []
        train, test, train_dates, test_dates, series = self.train_test_split(data=data, test_size= seq_length, model_name= model_name)

        data = train[['Close', 'ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband',
        'Mband', 'ketler']].values.reshape(-1, 1)
        
        data2 = test[['Close', 'ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband',
        'Mband', 'ketler']].values.reshape(-1, 1)
        # data = train[['Close', 'ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values
        # data2 = test[['Close', 'ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values    

        # Create sequences
        X_train, y_train = self.create_sequence(data, seq_length)
        X_val, y_val = self.create_sequence(data2, seq_length)

        model = Sequential()
        model.add(Input(shape=(seq_length, 1)))
        model.add(LSTM(50, activation='relu', return_sequences=True))
        model.add(Dropout(0.2))
        model.add(LSTM(50, activation='relu'))
        model.add(Dropout(0.2))
        model.add(Dense(1))

        model.compile(optimizer='adam', loss='mse')
        # model.compile(
        #     loss=MeanSquaredError(),
        #     optimizer=Adam(learning_rate=0.01),
        # )    
        model.summary()  

        callback = EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)

        history = model.fit(
            X_train, y_train, epochs=epochs, batch_size=batch_size,validation_data=(X_val, y_val),
            callbacks=[callback], verbose=0
        )

        return model, history        
    
    def model_metrics_Lstm(self, model, model_name, data, test_size):
        train, test, train_dates, test_dates, series = self.train_test_split(data, test_size, model_name)

        forecast = model.predict(test[['Close','ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values)
        actual_values = test['Close'].values
        
        # Mean Absolute Error (MAE)
        mae = mean_absolute_error(actual_values, forecast)

        # Root Mean Squared Error (RMSE)
        rmse = np.sqrt(mean_squared_error(actual_values, forecast))

        # Mean Absolute Percentage Error (MAPE)
        mape = np.mean(np.abs((actual_values - forecast) / actual_values)) * 100

        # Print the results
        print(f"Mean Absolute Error (MAE): {mae}")
        print(f"Root Mean Squared Error (RMSE): {rmse}")
        print(f"Mean Absolute Percentage Error (MAPE): {mape}%")   

    def plot_history(self, history):
        plt.figure(figsize=(12, 6))
        plt.plot(history.history['loss'])
        plt.plot(history.history['val_loss'])
        plt.title('LSTM Model Loss')
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.legend(['Train', 'Validation'], loc='upper left')
        plt.show()         

    def plot_actual_Vs_forecasted(self, data, test_size, model_name, model):
        plt.figure(figsize=(15, 8))
        train, test, train_dates, test_dates, series = self.train_test_split(data, test_size, model_name)
        plt.plot(test.index, test['Close'], label='Actual', linewidth=2)
        forecast = model.predict(test[['Close','ATR', 'Bhband', 'Bhband_indicator', 'Bma', 'Dhband', 'Dlband', 'Mband', 'ketler']].values)

        plt.plot(test.index, forecast, label=f' Prediction', linestyle='--')

        plt.title('Model Predictions Comparison')
        plt.xlabel('Date')
        plt.ylabel("Price")
        plt.legend()
        plt.show()        