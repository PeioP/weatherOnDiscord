import asyncio
from io import BytesIO
import discord
from discord.ext import commands, tasks
import numpy as np
import openmeteo_requests
from datetime import datetime, timedelta
import requests_cache
import matplotlib.pyplot as plt
import pandas as pd
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/meteofrance"
params = {
	"latitude": 48.112, #Rennes, FRANCE
	"longitude": -1.6743,
	"current": "temperature_2m",
	"daily": ["temperature_2m_max", "temperature_2m_min", "daylight_duration", "precipitation_sum"],
	"hourly": ["temperature_2m", "apparent_temperature", "precipitation"],
    "timezone": "Europe/Berlin",
	"forecast_days": 1
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

token_bot = 'your_token_bot'
channel_ID = 'your_channel_id'

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    send_message_daily.start()

@bot.command(name='hello')
async def hello(ctx):
    await ctx.send('Hello you')

@bot.command(name='meteo')
async def meteo_command(ctx):
    await meteo()

@tasks.loop(hours=24)
async def send_message_daily():  
    now = datetime.utcnow()
     
    # Set the sending time at 20h00 UTC+1
    send_time = datetime(now.year, now.month, now.day, 19, 0, 0)

    # ad one day if the sending time is in the past
    if now > send_time:
        send_time += timedelta(days=1)

    # Calculate the time until the sending time
    time_until_send = (send_time - now).total_seconds()

    # Wait until the sending time comes
    await asyncio.sleep(time_until_send)

    await meteo()

async def meteo():
    now = datetime.utcnow()

    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/meteofrance"
    params = {
        "latitude": 48.112,
        "longitude": -1.6743,
        "current": "temperature_2m",
        "hourly": ["temperature_2m", "apparent_temperature", "precipitation"],
        "timezone": "Europe/Berlin",
        "forecast_days": 1
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    # Current values. The order of variables needs to be the same as requested.
    current = response.Current()
    current_temperature_2m = current.Variables(0).Value()

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_apparent_temperature = hourly.Variables(1).ValuesAsNumpy()
    hourly_precipitation = hourly.Variables(2).ValuesAsNumpy()

    hourly_data = {"date": pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s"),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s"),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )}
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["apparent_temperature"] = hourly_apparent_temperature
    hourly_data["precipitation"] = hourly_precipitation

    hourly_dataframe = pd.DataFrame(data = hourly_data)

    vecteur = np.arange(24)
    # Create the graph
    plt.figure(figsize=(10, 6))
    plt.grid(True, linestyle='--', alpha=0.7)

    plt.figure(figsize=(10, 6))

    plt.plot(vecteur, hourly_dataframe['temperature_2m'], label='Temperature (°C)')
    plt.plot(vecteur, hourly_dataframe['apparent_temperature'], label='Apparent temperature (°C)')
    plt.plot(vecteur, hourly_dataframe['precipitation'], label= 'Precipitation (mm)')
    plt.axvline(x=(now.hour+1)+(now.minute/60), color='r', linestyle='--', label='Sending time')
    plt.axhline(y=0, color='k', linestyle='-')
    plt.xticks(np.arange(min(vecteur), max(vecteur)+1, 1.0))
    plt.xlabel('Hour')
    plt.ylabel('Temperature (°C)')
    plt.title('Today\'s little weather forecast')
    plt.legend()

    # Display the graph with tight layout
    plt.tight_layout()

    # Save the graph in a BytesIO object
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    channel = bot.get_channel(channel_ID) #channel id
    if channel:
        if now.minute < 10:
            if now.month>=10:
                await channel.send(
                    f'It\'s {now.hour+1}h0{now.minute}, it\'s {now.day}/{now.month}/{now.year}:\n'
                    f'The current temperature is: {current_temperature_2m:.2f} °C\n',
                    file=discord.File(buffer, 'temperature_graph.png')
                )
            else:    
                await channel.send(
                    f'It\'s {now.hour+1}h0{now.minute}, it\'s {now.day}/0{now.month}/{now.year}:\n'
                    f'The current temperature is: {current_temperature_2m:.2f} °C\n',
                    file=discord.File(buffer, 'temperature_graph.png')
                )
        else:
            if now.month>=10:
                await channel.send(
                    f'It\'s {now.hour+1}h{now.minute}, it\'s {now.day}/{now.month}/{now.year}:\n'
                    f'The current temperature is: {current_temperature_2m:.2f} °C\n',
                    file=discord.File(buffer, 'temperature_graph.png')
                )
            else:    
                await channel.send(
                    f'It\'s {now.hour+1}h{now.minute}, it\'s {now.day}/0{now.month}/{now.year}:\n'
                    f'The current temperature is: {current_temperature_2m:.2f} °C\n',
                    file=discord.File(buffer, 'temperature_graph.png')
                )

bot.run(token_bot)

