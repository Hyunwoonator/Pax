import discord
from discord.ui import Button, View
#from utilities import *
from perspective import analyze_text, main
#from initial_tests import INITIAL_TEST
from google import genai
from dotenv import load_dotenv
import datetime
import os
import ast

# Setup for Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
hasBeenTagged = True

# dotenv loading and the Gemini API Key
load_dotenv()
geminiKey = os.getenv("GENAI_API_KEY")
discordkey = os.getenv("token")
google_client = genai.Client(api_key=geminiKey)


@client.event
async def on_ready():
    print(f'WE have logged in as {client.user}')


@client.event
async def on_message(message):
    global hasBeenTagged

    if message.author == client.user:
        return

    if hasBeenTagged and "report" in message.content:
        await report(message)
        return

    if client.user.mentioned_in(message) and not hasBeenTagged:
        hasBeenTagged = True
        await message.channel.send("Pax has started logging messages.")
        return

    if hasBeenTagged and "config" in message.content:
        await display_configs(message)
        return

    # INITIAL TEST
    with open("settings.txt", "r") as f:
        bypass_test_1 = f.readlines()[0].split(":")[1].strip() == "True"

    # if not bypass_test_1:
    #     flagged_1 = await INITIAL_TEST(message, 1) == 1
    #     print("FLAGGED BY INITIAL TEST" if flagged_1 else "NOT FLAGGED")
    # else:
    #     flagged_1 = True

    flagged_1 = True

    if flagged_1:
        try:
            result, parsed = main(message.content)
        except Exception as e:
            print(f"Error in perspective analysis: {e}")
            return
        
        # Check if result is valid
        if not result or not isinstance(result, dict):
            print("Invalid result from perspective API")
            return

        categories = [
            "TOXICITY", "SEVERE_TOXICITY", "IDENTITY_ATTACK",
            "INSULT", "PROFANITY", "THREAT",
            "SEXUALLY_EXPLICIT", "FLIRTATION"
        ]

        with open("settings.txt", "r") as f:
            thresholds = list(map(float, f.readlines()[1].split(":")[1].strip().split(",")))

        flagged_categories = [categories[i] for i in range(len(categories)) if categories[i] in result and result[categories[i]] > thresholds[i]]
        print(flagged_categories if flagged_categories else "NOT FLAGGED FOR SECOND TEST")
        
        await get_context(message)
        
        # Fixed: reverse() returns None, use reversed() or slicing
        context_list = []
        with open("chatlogs.txt", "r", encoding="utf-8") as f:
            context_list = list(reversed(f.readlines()))
        
        # Get AI determination with proper error handling
        try:
            determine_warning_response = google_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Determine if {message.author} has violated online safety, according to this context list: {context_list}. Make SURE {message.author} TRULY deserves a warning, as this would possibly result in their banning from the server. If yes, output TRUE and ONLY the WORD 'TRUE', if no, output FALSE and ONLY the WORD 'FALSE'"
            )
            determine_warning = determine_warning_response.text.strip().upper()
        except Exception as e:
            print(f"Error getting AI determination: {e}")
            determine_warning = "FALSE"
        
        print(f"AI Determination: {determine_warning}")

        # Fixed: Compare the actual text content, not the object
        if determine_warning == "TRUE":
            if flagged_categories:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, your message was removed for violating community guidelines.", delete_after=10
                )
                reason = ", ".join(flagged_categories)
                with open("reputation.txt", "a", encoding="utf-8") as f:
                    f.write(str(message.author) + "\n")

                try:
                    determine_severity_str = google_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=f"Explanation of why message is bad. Here is user message: {message.content}. No affirmations, just explain but be brief (under 100 words). Explain how it can lead to a ban (this is a Discord server). ONE PARAGRAPH. Here is what sentimence detector flagged it as: {flagged_categories}. Use normal english formatting."
                    ).text
                except Exception as e:
                    print(f"Error getting severity explanation: {e}")
                    determine_severity_str = "This message violated community guidelines."

                try:
                    determine_severity = ast.literal_eval(determine_severity_str)
                except:
                    determine_severity = []

                for username in determine_severity:
                    user_obj = discord.utils.get(message.guild.members, name=username)
                    if user_obj:
                        await user_obj.send("You have violated policy")

                count = sum(1 for line in open("reputation.txt", "r", encoding="utf-8") if line.strip() == str(message.author))

                embed = discord.Embed(
                    title="⚠️ Message Flagged for Review",
                    description=f"Your recent message has been flagged by our moderation system. This is offense number {count}.",
                    color=discord.Color.orange() 
                )
                embed.add_field(name="Your Message", value=f"```{message.content[:100]}```", inline=False)
                embed.add_field(name="Why was this flagged?", value=f"Detected: {reason} \n \n {determine_severity_str}", inline=False)
                embed.add_field(name="What happens now?", value="A moderator will review your message. Please be respectful in your communications.", inline=False)
                embed.set_footer(text="Pax - Promoting peaceful communities")
                
                try:
                    await message.author.send(embed=embed)
                except discord.Forbidden:
                    print(f"Cannot send DM to {message.author}")

                # Notify moderators
                guild = message.guild

                mod_channel = discord.utils.get(guild.text_channels, name="mods")
                if (mod_channel):
                    class ModActionView(View):
                        def __init__(self, target_user: discord.Member, author: discord.Member):
                            super().__init__(timeout=180)  # 180-second timeout for the view
                            self.target_user = target_user
                            self.author = author # The moderator who initiated the action

                        # --- KICK BUTTON (FIXED) ---
                        @discord.ui.button(label="Kick", style=discord.ButtonStyle.secondary, emoji="👢")
                        async def kick_button(self, button: Button, interaction: discord.Interaction):
                            
                            # --- Permission Checks (Moved to the top) ---
                            # 1. Check if the moderator has kick permissions
                            if not interaction.user.guild_permissions.kick_members:
                                await interaction.response.send_message("You don't have permission to kick users.", ephemeral=True)
                                return

                            # 2. Check role hierarchy
                            if self.target_user.top_role >= interaction.user.top_role:
                                await interaction.response.send_message("You cannot kick this user (they have a higher or equal role).", ephemeral=True)
                                return

                            # --- Action (Now inside a single try/except) ---
                            try:
                                # 3. Kick the user (Only happens ONCE now)
                                await self.target_user.kick(reason=f"Kicked by {interaction.user.name} via bot.")
                                
                                # Update the original embed/message
                                new_embed = interaction.message.embeds[0]
                                new_embed.title = f"✅ User Kicked: {self.target_user.display_name}"
                                new_embed.color = discord.Color.orange()
                                new_embed.clear_fields() # Remove old fields
                                new_embed.add_field(name="Action Taken", value=f"Kicked by {interaction.user.mention}", inline=False)
                                
                                # Disable all buttons after an action is taken
                                for item in self.children:
                                    item.disabled = True
                                
                                await interaction.response.edit_message(embed=new_embed, view=self)

                            except discord.Forbidden:
                                await interaction.response.send_message("I don't have permissions to kick this user.", ephemeral=True)
                            except Exception as e:
                                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

                        # --- BAN BUTTON ---
                        @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🔨")
                        async def ban_button(self, button: Button, interaction: discord.Interaction):
                            # --- Permission Check ---
                            if not interaction.user.guild_permissions.ban_members:
                                await interaction.response.send_message("You don't have permission to ban users.", ephemeral=True)
                                return
                                
                            if self.target_user.top_role >= interaction.user.top_role:
                                await interaction.response.send_message("You cannot ban this user (they have a higher or equal role).", ephemeral=True)
                                return

                            # --- Action ---
                            try:
                                await self.target_user.ban(reason=f"Banned by {interaction.user.name} via bot.", delete_message_days=0)
                                
                                new_embed = interaction.message.embeds[0]
                                new_embed.title = f"⛔ User Banned: {self.target_user.display_name}"
                                new_embed.color = discord.Color.dark_red()
                                new_embed.clear_fields()
                                new_embed.add_field(name="Action Taken", value=f"Banned by {interaction.user.mention}", inline=False)

                                for item in self.children:
                                    item.disabled = True
                                
                                await interaction.response.edit_message(embed=new_embed, view=self)

                            except discord.Forbidden:
                                await interaction.response.send_message("I don't have permissions to ban this user.", ephemeral=True)
                            except Exception as e:
                                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

                        # --- MUTE (TIMEOUT) BUTTON ---
                        @discord.ui.button(label="Mute (1h)", style=discord.ButtonStyle.primary, emoji="🔇")
                        async def mute_button(self, button: Button, interaction: discord.Interaction):
                            # --- Permission Check ---
                            if not interaction.user.guild_permissions.moderate_members:
                                await interaction.response.send_message("You don't have permission to timeout users.", ephemeral=True)
                                return

                            if self.target_user.top_role >= interaction.user.top_role:
                                await interaction.response.send_message("You cannot mute this user (they have a higher or equal role).", ephemeral=True)
                                return

                            # --- Action ---
                            try:
                                duration = datetime.timedelta(hours=1)
                                await self.target_user.timeout(duration, reason=f"Muted by {interaction.user.name} via bot.")
                                
                                new_embed = interaction.message.embeds[0]
                                new_embed.title = f"🔇 User Muted: {self.target_user.display_name}"
                                new_embed.color = discord.Color.blue()
                                new_embed.clear_fields()
                                new_embed.add_field(name="Action Taken", value=f"Muted for 1 hour by {interaction.user.mention}", inline=False)

                                for item in self.children:
                                    item.disabled = True
                                
                                await interaction.response.edit_message(embed=new_embed, view=self)

                            except discord.Forbidden:
                                await interaction.response.send_message("I don't have permissions to mute this user.", ephemeral=True)
                            except Exception as e:
                                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
                                
                        # Optional: Add a check to ensure only the mod who ran the command can use it
                        async def interaction_check(self, interaction: discord.Interaction) -> bool:
                            if interaction.user.guild_permissions.manage_messages:
                                return True
                            else:
                                await interaction.response.send_message("You are not authorized to use these buttons.", ephemeral=True)
                                return False

                    embed = discord.Embed(
                        title="🚨 Moderation Alert: Harmful Message",
                        description=f"A potentially harmful message from {message.author.mention} has been detected.",
                        color=discord.Color.red(),
                        timestamp=message.created_at
                    )
                    embed.set_author(
                        name=f"{message.author.display_name} ({message.author.id})",
                        icon_url=message.author.display_avatar.url
                    )
                    embed.add_field(name="User", value=f"{message.author.mention}", inline=True)
                    embed.add_field(name="Total Offenses", value=f"**{count}**", inline=True)
                    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                    embed.add_field(name="Message Content", value=f"```{message.content[:1000]}```", inline=False)
                    embed.add_field(name="Take Action", value=f"[Click here to jump to the message]({message.jump_url})", inline=False)
                    embed.add_field(name="Why was this flagged?", value=f"Detected: {reason} \n \n {determine_severity_str}", inline=False)
                    embed.set_footer(text=f"Bot Alert System | Guild: {message.guild.name}")

                    view = ModActionView(target_user=message.author, author=None)
                    await mod_channel.send(embed=embed, view=view)


async def display_configs(message):
    parts = message.content.split(" ")
    if len(parts) < 3:
        await message.channel.send("Usage: config <index> <value>")
        return

    try:
        index = int(parts[1])
        value = parts[2]
    except (ValueError, IndexError):
        await message.channel.send("Invalid format. Usage: config <index> <value>")
        return

    try:
        with open("settings.txt", "r+", encoding="utf-8") as f:
            lines = f.readlines()
            thresholds = lines[1].split(":")[1].strip().split(",")
            
            if index < 0 or index >= len(thresholds):
                await message.channel.send(f"Index out of range. Valid range: 0-{len(thresholds)-1}")
                return
            
            thresholds[index] = value
            lines[1] = f"thresholds:{','.join(thresholds)}\n"
            f.seek(0)
            f.writelines(lines)
            f.truncate()

        await message.channel.send(f"✅ Updated config index {index} to {value}")
    except Exception as e:
        await message.channel.send(f"Error updating config: {e}")


async def get_context(message):
    try:
        with open("chatlogs.txt", "w", encoding="utf-8") as f:
            async for msg in message.channel.history(limit=10):
                f.write(f"Author {msg.author}: {msg.content}\n")
    except Exception as e:
        print(f"Error getting context: {e}")

    
async def report(message):
    try:
        with open("chatlogs.txt", "r", encoding="utf-8") as f:
            report_content = f.read()
        await message.channel.send("REPORT:\n" + report_content[:1900])
    except FileNotFoundError:
        await message.channel.send("No chat logs available.")
    except Exception as e:
        await message.channel.send(f"Error retrieving report: {e}")


# Never hardcode token in production
client.run(discordkey)