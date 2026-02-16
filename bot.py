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

RED = 0xff0000

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
        await interaction.followup.send("🧾 Carrinho criado!", ephemeral=True)

class StorePanelView(ui.View):
    def __init__(self, pid, plans):
        super().__init__(timeout=None)
        self.add_item(PlanSelect(pid, plans))

# ========= CARRINHO =========
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
            return int(base * (1 - self.discount/100))
        return base

    def make_embed(self):
        prod, plan = self.get()
        e = discord.Embed(title=f"🛒 {prod['name']}", color=RED)
        e.add_field(name="Plano", value=plan["name"])
        e.add_field(name="Preço", value=f"R$ {plan['price']}")
        e.add_field(name="Qtd", value=self.qtd)
        if self.discount:
            e.add_field(name="Cupom", value=f"{self.discount}%")
        e.add_field(name="Total", value=f"R$ {self.total()}", inline=False)
        e.set_footer(text="Status: aguardando pagamento")
        return e

    async def refresh(self, i):
        await i.message.edit(embed=self.make_embed(), view=self)

    @ui.button(label="➕", style=discord.ButtonStyle.secondary)
    async def plus(self, i, _):
        if i.user.id != self.user_id: return
        self.qtd += 1
        await self.refresh(i)

    @ui.button(label="➖", style=discord.ButtonStyle.secondary)
    async def minus(self, i, _):
        if i.user.id != self.user_id: return
        if self.qtd > 1: self.qtd -= 1
        await self.refresh(i)

    @ui.button(label="🎟️ Cupom", style=discord.ButtonStyle.primary)
    async def cupom(self, i, _):
        await i.response.send_message("Envie o código do cupom:", ephemeral=True)
        def check(m): return m.author.id == self.user_id and m.channel == i.channel
        msg = await bot.wait_for("message", check=check)
        d = load_cupons()
        code = msg.content.upper()
        if code in d:
            self.discount = d[code]
            await self.refresh(i)
            await i.followup.send("✅ Cupom aplicado!", ephemeral=True)
        else:
            await i.followup.send("❌ Cupom inválido", ephemeral=True)

    @ui.button(label="💳 Pagar", style=discord.ButtonStyle.success)
    async def pay(self, i, _):
        prod,_ = self.get()
        e = discord.Embed(
            title="💳 PAGAMENTO VIA PIX",
            description="Escaneie o QR ou copie a chave.\nEnvie o comprovante aqui.",
            color=RED
        )
        e.add_field(name="Chave", value=f"`{prod['pix']}`", inline=False)
        e.add_field(name="Total", value=f"R$ {self.total()}", inline=False)
        if PIX_QR_URL.startswith("http"):
    e.set_image(url=PIX_QR_URL)

        await i.response.send_message(embed=e)

# ========= CRIAR PRODUTO =========
@bot.command()
async def loja_criar(ctx):
    if not is_staff(ctx.author): return
    def check(m): return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("Nome do produto:")
    nome = (await bot.wait_for("message", check=check)).content

    await ctx.send("Descrição:")
    descricao = (await bot.wait_for("message", check=check)).content

    await ctx.send("Imagem (link ou upload):")
    msg = await bot.wait_for("message", check=check)
    imagem = msg.attachments[0].url if msg.attachments else msg.content

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

        plans[f"p{i}"] = {"name": pname, "price": pprice, "stock": pstock}

        await ctx.send("Outro plano? (s/n)")
        if (await bot.wait_for("message", check=check)).content.lower() != "s":
            break
        i += 1

    data = load_products()
    pid = str(len(data)+1)
    data[pid] = {"name": nome, "desc": descricao, "img": imagem, "pix": pix, "plans": plans}
    save_products(data)

    embed = discord.Embed(title=nome, description=descricao, color=RED)
    embed.set_image(url=imagem)

    await ctx.send(embed=embed, view=StorePanelView(pid, plans))

bot.run(TOKEN)

