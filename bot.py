import discord, json, os, asyncio
from discord.ext import commands, tasks
from discord import ui

# ========= CONFIG =========
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1469437008131653766

NEXT_HELPER = 1469446748635398164
OWNER = 1469446742843068507
STAFF_IDS = (NEXT_HELPER, OWNER)

PIX_QR_URL = "https://cdn.discordapp.com/attachments/1469446920136167616/1472850758436262092/pix.png"
PRODUCTS_FILE = "produtos.json"
COUPONS_FILE = "cupons.json"
ORDERS_FILE = "pedidos.json"

RED = 0xff0000




#========= aura v2

async def dm_with_button(user_id, embed, channel_id):
    try:
        user = await bot.fetch_user(user_id)
        link = channel_link(GUILD_ID, channel_id)

        view = ui.View()
        view.add_item(
            discord.ui.Button(label="Ir para meu ticket", url=link)
        )

        await user.send(embed=embed, view=view)
    except:
        pass


#===== DMSSSSS ==========


async def dm_user(user_id, embed):
    try:
        user = await bot.fetch_user(user_id)
        await user.send(embed=embed)
    except:
        pass




# ========= BOT =========
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= STATUS =========
@tasks.loop(seconds=15)
async def status_loop():
    sts = ["🛒 Loja Online", "💳 Pagamento PIX", "🔥 Next Community"]
    for s in sts:
        await bot.change_presence(activity=discord.Game(s))
        await asyncio.sleep(15)

@bot.event
async def on_ready():
    status_loop.start()
    print(f"🤖 Conectado como {bot.user}")

# ========= STAFF SAFE =========
def is_staff(member):
    if not member:
        return False
    if not hasattr(member, "roles"):
        guild = bot.get_guild(GUILD_ID)
        if guild:
            member = guild.get_member(member.id)
    if not member:
        return False
    return any(r.id in STAFF_IDS for r in member.roles)

# ========= JSON =========
def load_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_orders():
    return load_json(ORDERS_FILE)

def save_orders(d):
    save_json(ORDERS_FILE, d)


# ========= CUPONS =========
def load_cupons(): return load_json(COUPONS_FILE)
def save_cupons(d): save_json(COUPONS_FILE, d)

@bot.command()
async def cupom(ctx, nome, desconto: int):
    if not is_staff(ctx.author): return
    d = load_cupons()
    d[nome.upper()] = desconto
    save_cupons(d)
    await ctx.send(f"🎟️ Cupom `{nome}` criado com {desconto}%")

# ========= PRODUTOS =========
def load_products(): return load_json(PRODUCTS_FILE)
def save_products(d): save_json(PRODUCTS_FILE, d)

# ========= SELECT =========
class PlanSelect(ui.Select):
    def __init__(self, pid, plans):
        options = [
            discord.SelectOption(
                label=p["name"],
                description=f"R$ {p['price']} | Estoque {p['stock']}",
                value=k
            ) for k,p in plans.items()
        ]
        super().__init__(placeholder="Escolha um plano", options=options)
        self.pid = pid

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = load_products()
        prod = data[self.pid]

        thread = await interaction.channel.create_thread(
            name=f"{prod['name']} - {interaction.user.name}",
            type=discord.ChannelType.private_thread
        )
        await thread.add_user(interaction.user)

        view = CartView(self.pid, self.values[0], interaction.user.id)
        await thread.send(embed=view.make_embed(), view=view)
        link = channel_link(GUILD_ID, thread.id)

 view = ui.View()
view.add_item(
    discord.ui.Button(label="🧾 Ir para o carrinho", url=link)
)

await interaction.followup.send(
    "🧾 Carrinho criado!",
    view=view,
    ephemeral=True
)


class StorePanelView(ui.View):
    def __init__(self, pid, plans):
        super().__init__(timeout=None)
        self.add_item(PlanSelect(pid, plans))

class CartView(ui.View):
    def __init__(self, pid, plan_id, user_id):
        super().__init__(timeout=None)
        self.pid = pid
        self.plan_id = plan_id
        self.user_id = user_id
        self.qtd = 1
        self.discount = 0

    def get(self):
        data = load_products()
        prod = data[self.pid]
        plan = prod["plans"][self.plan_id]
        return prod, plan

    def total(self):
        prod, plan = self.get()
        base = plan["price"] * self.qtd
        if self.discount:
            return int(base * (1 - self.discount / 100))
        return base

    def make_embed(self):
        prod, plan = self.get()
        e = discord.Embed(title=f"🛒 {prod['name']}", color=RED)
        e.add_field(name="Plano", value=plan["name"])
        e.add_field(name="Preço", value=f"R$ {plan['price']}")
        e.add_field(name="Quantidade", value=self.qtd)
        if self.discount:
            e.add_field(name="Cupom", value=f"{self.discount}%")
        e.add_field(name="Total", value=f"R$ {self.total()}", inline=False)
        status = load_orders().get(str(self.user_id), {}).get("status", "Aguardando Pagamento")
        e.set_footer(text=f"Status: {status}")
        return e

    async def refresh(self, interaction):
        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )

    @ui.button(label="➕", style=discord.ButtonStyle.secondary)
    async def plus(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Não é seu carrinho", ephemeral=True)
            return
        self.qtd += 1
        await self.refresh(interaction)

    @ui.button(label="➖", style=discord.ButtonStyle.secondary)
    async def minus(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Não é seu carrinho", ephemeral=True)
            return
        if self.qtd > 1:
            self.qtd -= 1
        await self.refresh(interaction)

    @ui.button(label="🎟️ Cupom", style=discord.ButtonStyle.primary)
    async def aplicar_cupom(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Não é seu carrinho", ephemeral=True)
            return

        await interaction.response.send_message(
            "Envie o código do cupom:",
            ephemeral=True
        )

        def check(m):
            return m.author.id == self.user_id and m.channel == interaction.channel

        msg = await bot.wait_for("message", check=check)
        cupons = load_cupons()
        code = msg.content.upper()

        if code in cupons:
            self.discount = cupons[code]
            await interaction.followup.send("✅ Cupom aplicado!", ephemeral=True)
            await interaction.message.edit(embed=self.make_embed(), view=self)
        else:
            await interaction.followup.send("❌ Cupom inválido", ephemeral=True)

    @ui.button(label="💳 Pagar", style=discord.ButtonStyle.success)
    async def pay(self, i, _):
        prod, _ = self.get()

        orders = load_orders()
        orders[str(i.channel.id)] = {
            "user_id": self.user_id,
            "channel_id": i.channel.id,
            "message_id": i.message.id,
            "status": "Aguardando Pagamento"
        }
        save_orders(orders)

        e = discord.Embed(
            title="💳 PAGAMENTO VIA PIX",
            description="Escaneie o QR ou copie a chave.\nEnvie o comprovante aqui.",
            color=RED
        )

        e.add_field(name="Chave PIX", value=f"`{prod['pix']}`", inline=False)
        e.add_field(name="Total", value=f"R$ {self.total()}", inline=False)

        if PIX_QR_URL.startswith("http"):
            e.set_image(url=PIX_QR_URL)

        await i.response.send_message(embed=e)

# ============ clear ============

@bot.command()
async def clear(ctx, n: int = None):
    if not is_staff(ctx.author):
        return

    if n is None:
        await ctx.channel.purge()
        await ctx.send("🧹 Chat limpo!", delete_after=3)
    else:
        await ctx.channel.purge(limit=n+1)
        await ctx.send(f"🧹 {n} mensagens apagadas!", delete_after=3)

# ================ Entregar =================


@bot.command()
async def finalizar(ctx):
    if not is_staff(ctx.author):
        return

    orders = load_orders()
    channel_id = ctx.channel.id
    order = orders.get(str(channel_id))

    embed = discord.Embed(
        title="📦 PEDIDO ENTREGUE",
        description="Seu pedido foi entregue com sucesso!\nObrigado por comprar na **Next Community** 💚",
        color=0x00ff99
    )

    await ctx.send(embed=embed)

    if order:
        dm = discord.Embed(
            title="📦 Pedido finalizado",
            description="Seu pedido foi entregue com sucesso!\nObrigado pela preferência 💚",
            color=0x00ff99
        )
        await dm_with_button(order["user_id"], dm, order["channel_id"])

    # apagar msg do staff
    await asyncio.sleep(4)
    try:
        await ctx.message.delete()
    except:
        pass

    # fechar thread em 60s
    await asyncio.sleep(60)
    try:
        await ctx.channel.delete()
    except:
        pass




# ============== Reprovar ================





@bot.command()
async def reprovar(ctx, *, motivo):
    if not is_staff(ctx.author):
        return

    orders = load_orders()
    channel_id = ctx.channel.id

    order = orders.get(str(channel_id))
    if not order:
        return await ctx.send("❌ Nenhum pedido encontrado nesta thread.")

    order["status"] = "Pagamento Reprovado"
    save_orders(orders)

    channel = bot.get_channel(order["channel_id"])
    msg = await channel.fetch_message(order["message_id"])

    embed = msg.embeds[0]
    embed.set_footer(text="Status: Pagamento Reprovado")
    await msg.edit(embed=embed)

    embed_thread = discord.Embed(
        title="❌ PAGAMENTO REPROVADO",
        color=0xe74c3c
    )
    embed_thread.add_field(name="Motivo:", value=motivo, inline=False)

    await ctx.send(embed=embed_thread)

    # DM
    dm = discord.Embed(
        title="❌ Pedido reprovado",
        description=f"Seu pagamento foi reprovado.\n\n**Motivo:** {motivo}",
        color=0xe74c3c
    )
    await dm_with_button(order["user_id"], dm, order["channel_id"])

    # apagar msg do staff
    await asyncio.sleep(4)
    try:
        await ctx.message.delete()
    except:
        pass

    # fechar thread após 30s
    await asyncio.sleep(30)
    try:
        await ctx.channel.delete()
    except:
        pass





class GoToCartView(ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @ui.button(label="🧾 Ir para o carrinho", style=discord.ButtonStyle.link)
    async def go(self, interaction, _):
        pass


# ====== funcao aura =========


def channel_link(guild_id, channel_id):
    return f"https://discord.com/channels/{guild_id}/{channel_id}"



# ============= Aprovar ==============



@bot.command()
async def aprovar(ctx):
    if not is_staff(ctx.author):
        return

    orders = load_orders()
    channel_id = ctx.channel.id

    order = orders.get(str(channel_id))
    if not order:
        return await ctx.send("❌ Nenhum pedido encontrado nesta thread.")

    order["status"] = "Pagamento Aprovado"
    save_orders(orders)

    channel = bot.get_channel(order["channel_id"])
    msg = await channel.fetch_message(order["message_id"])

    embed = msg.embeds[0]
    embed.set_footer(text="Status: Pagamento Aprovado")
    await msg.edit(embed=embed)

    embed_thread = discord.Embed(
        title="✅ PAGAMENTO APROVADO",
        description="Pagamento confirmado.\nAguarde a entrega.",
        color=0x2ecc71
    )
    await ctx.send(embed=embed_thread)

    # DM
    dm = discord.Embed(
        title="✅ Pedido aprovado",
        description="Seu pagamento foi aprovado!\nA entrega será feita no mesmo canal.",
        color=0x2ecc71
    )
    await dm_with_button(order["user_id"], dm, order["channel_id"])

    # apagar msg do staff
    await asyncio.sleep(4)
    try:
        await ctx.message.delete()
    except:
        pass



# ========= CRIAR PRODUTO =========
@bot.command()
async def loja_criar(ctx):
    if not is_staff(ctx.author):
        return

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("🛍️ Criando produto\nNome do produto:")
    nome = (await bot.wait_for("message", check=check)).content

    await ctx.send("Descrição:")
    descricao = (await bot.wait_for("message", check=check)).content

    await ctx.send("Imagem (link, upload ou N para não usar):")
    msg = await bot.wait_for("message", check=check)

    if msg.content.upper() == "N":
        imagem = None
    elif msg.attachments:
        imagem = msg.attachments[0].url
    else:
        imagem = msg.content.strip()

    await ctx.send("Chave PIX:")
    pix = (await bot.wait_for("message", check=check)).content

    plans = {}
    i = 1
    while True:
        await ctx.send(f"Plano {i} nome:")
        pname = (await bot.wait_for("message", check=check)).content

        await ctx.send("Preço:")
        pprice = int((await bot.wait_for("message", check=check)).content)

        await ctx.send("Estoque:")
        pstock = int((await bot.wait_for("message", check=check)).content)

        plans[f"p{i}"] = {
            "name": pname,
            "price": pprice,
            "stock": pstock
        }

        await ctx.send("Outro plano? (s/n)")
        if (await bot.wait_for("message", check=check)).content.lower() != "s":
            break
        i += 1

    data = load_products()
    pid = str(len(data) + 1)

    data[pid] = {
        "name": nome,
        "desc": descricao,
        "img": imagem,
        "pix": pix,
        "plans": plans
    }

    save_products(data)

    embed = discord.Embed(title=nome, description=descricao, color=RED)

    if imagem and imagem.startswith("http"):
        embed.set_image(url=imagem)

    await ctx.send(embed=embed, view=StorePanelView(pid, plans))


bot.run(TOKEN)













