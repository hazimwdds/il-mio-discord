import discord 
from discord.ext import commands
from discord.ext.commands import Bot, CommandNotFound
from discord import app_commands
from config import TOKEN, ROLE_TO_ADD, ROLE_TO_REMOVE, REPORT_CHANNEL_ID, STAFF_ROLE_ID, SUGGESTION_CHANNEL_ID, TICKET_CHANNEL_ID, LOG_CHANNEL_ID
import random
import asyncio
import string

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

report_data = {}
suggestion_data = {}
active_captchas = {}
active_tickets = {}

# Funzioni di utilità
def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_unique_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Funzione per inviare un messaggio al canale di log
async def log_event(message: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(message)

class AutoModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class EventLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        @bot.event
        async def on_member_join(member: discord.Member):
            role = discord.Object(id=ROLE_TO_REMOVE)
            await member.add_roles(role)
            log_message = f"**MEMBER JOIN**: {member.mention} ({member.id}) si è unito al server. Data di creazione: {member.created_at.strftime('%d/%m/%Y %H:%M:%S')}"
            await log_event(log_message)

        @bot.event
        async def on_member_remove(member: discord.Member):
            log_message = f"**MEMBER LEAVE**: {member.mention} ({member.id}) ha lasciato il server."
            await log_event(log_message)

        @bot.event
        async def on_message_edit(before: discord.Message, after: discord.Message):
            if before.author.bot:
                return
            log_message = f"**MESSAGE EDIT**: Messaggio di {before.author.mention} modificato nel canale {before.channel.mention}. \nPrima: {before.content}\nDopo: {after.content}"
            await log_event(log_message)

        @bot.event
        async def on_message_delete(message: discord.Message):
            if message.author.bot:
                return
            log_message = f"**MESSAGE DELETE**: Messaggio di {message.author.mention} eliminato nel canale {message.channel.mention}. Contenuto: {message.content}"
            await log_event(log_message)

        @bot.event
        async def on_channel_create(channel: discord.abc.GuildChannel):
            log_message = f"**CHANNEL CREATE**: Nuovo canale creato: {channel.mention} ({channel.id})"
            await log_event(log_message)

        @bot.event
        async def on_channel_delete(channel: discord.abc.GuildChannel):
            log_message = f"**CHANNEL DELETE**: Canale eliminato: {channel.name} ({channel.id})"
            await log_event(log_message)

        @bot.event
        async def on_command(ctx: commands.Context):
            log_message = f"**COMMAND USAGE**: Comando '{ctx.command}' usato da {ctx.author.mention} nel canale {ctx.channel.mention}."
            await log_event(log_message)

        @bot.event
        async def on_command_error(ctx: commands.Context, error: Exception):
            log_message = f"**COMMAND ERROR**: Errore nel comando '{ctx.command}' usato da {ctx.author.mention} nel canale {ctx.channel.mention}. Errore: {error}"
            await log_event(log_message)

@bot.event
async def on_ready():
    print(f'Siamo entrati come {bot.user}')
    await bot.tree.sync()
    print('Comandi slash sincronizzati')

@bot.tree.command(name="verify", description="Verifica il tuo account con CAPTCHA")
async def verify(interaction: discord.Interaction):
    user = interaction.user
    captcha_code = generate_captcha()
    active_captchas[user.id] = captcha_code

    await interaction.response.send_message(
        f"Per verificare il tuo account, rispondi a questo messaggio con il codice CAPTCHA: {captcha_code}. Hai 5 minuti per completare la verifica.",
        ephemeral=True
    )

    def check(m):
        return m.author == user and m.channel == interaction.channel and m.content == captcha_code

    try:
        msg = await bot.wait_for('message', check=check, timeout=300)
        await user.add_roles(discord.Object(id=ROLE_TO_ADD))
        await user.remove_roles(discord.Object(id=ROLE_TO_REMOVE))
        await interaction.followup.send("Verifica completata con successo!", ephemeral=True)
        log_message = f"**VERIFICATION PASSED**: {user.mention} ha completato la verifica con successo. Codice CAPTCHA: {captcha_code}."
        await log_event(log_message)
    except asyncio.TimeoutError:
        await interaction.followup.send("Tempo scaduto. Verifica non completata.", ephemeral=True)
    finally:
        if user.id in active_captchas:
            del active_captchas[user.id]

@bot.tree.command(name="kick", description="Espelle un utente")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.kick(reason=reason)
    await interaction.response.send_message(f'{member} è stato espulso. Motivo: {reason}')

@bot.tree.command(name="ban", description="Banna un utente")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.ban(reason=reason)
    await interaction.response.send_message(f'{member} è stato bannato. Motivo: {reason}')

@bot.tree.command(name="clear", description="Elimina un certo numero di messaggi")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f'{amount} messaggi sono stati eliminati.')

@bot.tree.command(name="tempban", description="Banna temporaneamente un utente")
@app_commands.checks.has_permissions(ban_members=True)
async def tempban(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
    await member.ban(reason=reason)
    await interaction.response.send_message(f'{member} è stato bannato per {duration} secondi. Motivo: {reason}')
    await asyncio.sleep(duration)
    await interaction.guild.unban(member)
    await interaction.channel.send(f'{member} è stato sbannato.')

@bot.tree.command(name="say", description="Invia un messaggio a un canale specifico")
async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message(f'Messaggio inviato a {channel.mention}')

@bot.tree.command(name="partnership", description="Crea una partnership")
async def partnership(interaction: discord.Interaction, manager: discord.Member, cliente: discord.Member, channel: discord.TextChannel):
    await interaction.response.send_message('Inserisci la descrizione della partnership:')
    
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    description_msg = await bot.wait_for('message', check=check)
    
    partnership_message = f'Partnership creata da: {manager.mention}\nCliente: {cliente.mention}\nDescrizione: {description_msg.content}'
    await channel.send(partnership_message)
    await interaction.response.send_message(f'Partnership inviata a {channel.mention}')

@bot.tree.command(name="sync_roles", description="Sincronizza i permessi dei canali con quelli della loro categoria")
@app_commands.checks.has_permissions(administrator=True)
async def sync_roles(interaction: discord.Interaction):
    guild = interaction.guild
    
    if not guild:
        await interaction.response.send_message("Il comando può essere eseguito solo all'interno di un server.", ephemeral=True)
        return
    
    category_permissions = {}
    
    for category in guild.categories:
        category_permissions[category.id] = {
            'default': category.overwrites_for(guild.default_role),
            'overwrites': {role.id: category.overwrites_for(role) for role in guild.roles}
        }
    
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel) and channel.category:
            category_id = channel.category.id
            category_perm = category_permissions.get(category_id)
            
            if category_perm:
                overwrites = category_perm['overwrites']
                overwrites[guild.default_role.id] = category_perm['default']
                try:
                    await channel.edit(overwrites=overwrites)
                except Exception as e:
                    await interaction.response.send_message(f"Errore nella sincronizzazione del canale {channel.name}: {str(e)}", ephemeral=True)
                    return
    
    await interaction.response.send_message("Sincronizzazione dei permessi completata con successo.")

@bot.tree.command(name="report", description="Segnala un utente al team di moderazione")
async def report(interaction: discord.Interaction, member: discord.Member, reason: str):
    report_id = generate_unique_id()
    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    
    if not report_channel:
        await interaction.response.send_message("Canale di segnalazione non trovato.", ephemeral=True)
        return
    
    report_message = f"**[ID Segnalazione: {report_id}]**\nSegnalato da: {interaction.user.mention}\nUtente Segnalato: {member.mention}\nMotivo: {reason}"
    await report_channel.send(report_message)
    await interaction.response.send_message("La segnalazione è stata inviata al team di moderazione.", ephemeral=True)

    report_data[report_id] = {'reporter': interaction.user, 'reported': member, 'reason': reason}

@bot.tree.command(name="suggestion", description="Suggerisci una nuova funzionalità o miglioramento")
async def suggestion(interaction: discord.Interaction, suggestion: str):
    suggestion_id = generate_unique_id()
    suggestion_channel = bot.get_channel(SUGGESTION_CHANNEL_ID)
    
    if not suggestion_channel:
        await interaction.response.send_message("Canale di suggerimenti non trovato.", ephemeral=True)
        return
    
    suggestion_message = f"**[ID Suggerimento: {suggestion_id}]**\nProposto da: {interaction.user.mention}\nSuggerimento: {suggestion}"
    await suggestion_channel.send(suggestion_message)
    await interaction.response.send_message("Il tuo suggerimento è stato inviato.", ephemeral=True)

    suggestion_data[suggestion_id] = {'suggestor': interaction.user, 'suggestion': suggestion}

@bot.tree.command(name="ticket", description="Apri un ticket di supporto")
async def ticket(interaction: discord.Interaction, issue: str):
    ticket_id = generate_unique_id()
    ticket_channel = bot.get_channel(TICKET_CHANNEL_ID)
    
    if not ticket_channel:
        await interaction.response.send_message("Canale di ticket non trovato.", ephemeral=True)
        return
    
    ticket_message = f"**[ID Ticket: {ticket_id}]**\nAperto da: {interaction.user.mention}\nProblema: {issue}"
    await ticket_channel.send(ticket_message)
    await interaction.response.send_message("Il tuo ticket è stato inviato al supporto.", ephemeral=True)

    active_tickets[ticket_id] = {'user': interaction.user, 'issue': issue}

@bot.tree.command(name="close_ticket", description="Chiudi un ticket di supporto")
@app_commands.checks.has_role(STAFF_ROLE_ID)
async def close_ticket(interaction: discord.Interaction, ticket_id: str):
    ticket = active_tickets.get(ticket_id)
    
    if not ticket:
        await interaction.response.send_message("Ticket non trovato.", ephemeral=True)
        return
    
    del active_tickets[ticket_id]
    await interaction.response.send_message(f"Ticket {ticket_id} chiuso con successo.", ephemeral=True)

@bot.tree.command(name="close_report", description="Chiudi una segnalazione")
@app_commands.checks.has_role(STAFF_ROLE_ID)
async def close_report(interaction: discord.Interaction, report_id: str):
    report = report_data.get(report_id)
    
    if not report:
        await interaction.response.send_message("Segnalazione non trovata.", ephemeral=True)
        return
    
    del report_data[report_id]
    await interaction.response.send_message(f"Segnalazione {report_id} chiusa con successo.", ephemeral=True)

@bot.tree.command(name="close_suggestion", description="Chiudi un suggerimento")
@app_commands.checks.has_role(STAFF_ROLE_ID)
async def close_suggestion(interaction: discord.Interaction, suggestion_id: str):
    suggestion = suggestion_data.get(suggestion_id)
    
    if not suggestion:
        await interaction.response.send_message("Suggerimento non trovato.", ephemeral=True)
        return
    
    del suggestion_data[suggestion_id]
    await interaction.response.send_message(f"Suggerimento {suggestion_id} chiuso con successo.", ephemeral=True)

@bot.tree.command(name="mute", description="Silenzia un utente per un periodo di tempo specifico")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels:
            await channel.set_permissions(mute_role, speak=False, send_messages=False)

    await member.add_roles(mute_role)
    await interaction.response.send_message(f'{member.mention} è stato silenziato per {duration} minuti. Motivo: {reason}')
    await asyncio.sleep(duration * 60)
    await member.remove_roles(mute_role)
    await interaction.channel.send(f'{member.mention} è stato desilenziato.')

@bot.tree.command(name="unmute", description="Rimuovi il silenziamento di un utente")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await interaction.response.send_message(f'{member.mention} è stato desilenziato.')
    else:
        await interaction.response.send_message(f'{member.mention} non è silenziato.', ephemeral=True)

@bot.tree.command(name="warn", description="Avvisa un utente")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    warn_message = f"**AVVISO**: {member.mention}, hai ricevuto un avviso per: {reason}."
    await member.send(warn_message)
    await interaction.response.send_message(f'{member.mention} è stato avvisato. Motivo: {reason}')

@bot.tree.command(name="userinfo", description="Mostra informazioni su un utente")
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    roles = [role for role in member.roles]
    embed = discord.Embed(title=f"Informazioni su {member}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="ID Utente", value=member.id, inline=True)
    embed.add_field(name="Nome", value=member.display_name, inline=True)
    embed.add_field(name="Ruoli", value=" ".join([role.mention for role in roles]), inline=True)
    embed.add_field(name="Account creato", value=member.created_at.strftime('%d/%m/%Y %H:%M:%S'), inline=True)
    embed.add_field(name="Entrato nel server", value=member.joined_at.strftime('%d/%m/%Y %H:%M:%S'), inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Mostra informazioni sul server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Informazioni su {guild.name}", color=discord.Color.green())
    embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="ID Server", value=guild.id, inline=True)
    embed.add_field(name="Proprietario", value=guild.owner.mention, inline=True)
    embed.add_field(name="Membri", value=guild.member_count, inline=True)
    embed.add_field(name="Canali Testo", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Canali Vocali", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Creato il", value=guild.created_at.strftime('%d/%m/%Y %H:%M:%S'), inline=True)

    await interaction.response.send_message(embed=embed)

bot.add_cog(AutoModeration(bot))
bot.add_cog(EventLogger(bot))

bot.run(TOKEN)
