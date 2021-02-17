
import random

def calcLiquidity(c, r):
	n = c/(2*(1-r))
	y = c/(2*r)
	ls = 0
	if (n > c):
		# yes more likely
		y = c/n*y
		n = c
		ls = n*(1-r)*2
		# residual cash
		r_c = c-ls
		r_y = r_c / r
		r_n = 0
	else:
		# no more likely
		n = c/y*n
		y = c
		ls = y*r*2
		r_c = c-ls
		r_y = 0
		r_n = r_c / (1-r)
	return (y, n, r_y, r_n, ls)

LIQ_FEE = 0.02
# TODO: build in merge fees, sell orders

# due to the constant product rule, LPs are short convexity somewhat
class CPMM(object):

	def __init__(self):
		# initialize
		self.noShares = 0
		self.yesShares = 0
		# excess shares of liquidity pool
		self.noResidShares = 0
		self.yesResidShares = 0
		self.lps = {}
		self.trades = {}
		self.liqFees = {}
		self.stable = 0

	def distLiqFee(self, liqFee):
		totLiqShares = sum(self.lps.values())
		for lp in self.lps:
			if lp in self.liqFees:
				self.liqFees[lp] += self.lps[lp] / totLiqShares * liqFee
			else:
				self.liqFees[lp] = self.lps[lp] / totLiqShares * liqFee

	def getRate(self):
		return self.noShares / (self.noShares + self.yesShares)

	def getLiqFees(self):
		return self.liqFees

	def getLiqUsersValueWithFees(self):
		return self.getLiqUsersValue()+self.getLiqFeesValue()

	def getLiqUsersValue(self):
		return (self.getLiqPoolValue()+self.getLiqResidValue())

	def getLiqPoolValue(self):
		r = self.getRate()
		return self.yesShares*r+self.noShares*(1-r)

	def getLiqResidValue(self):
		r = self.getRate()
		return self.yesResidShares*r+self.noResidShares*(1-r)

	def getLiqFeesValue(self):
		return sum(self.liqFees.values())

	def getYesPotentialWin(self):
		return sum([self.trades[x]['yes'] for x in self.trades])

	def getNoPotentialWin(self):
		return sum([self.trades[x]['no'] for x in self.trades])

	def checkConsOfShares(self):
		# sum shares in pool + trades
		yesShares = self.yesShares + sum([self.trades[x]['yes'] for x in self.trades])
		noShares = self.noShares + sum([self.trades[x]['no'] for x in self.trades])
		#assert(round(yesShares) == round(noShares) == round(self.stable))
		print(yesShares)
		print(noShares)
		print(self.stable)

	'''def addTrade(self, addr, typ_, dir_, n, px):
		if addr in self.trades:
			self.trades[addr].append(Trade(typ_, dir_, n, px))
		else:
			self.trades[addr] = [Trade(typ_, dir_, n, px)]'''

	def addTrade(self, addr, typ_, dir_, n):
		if addr in self.trades:
			if typ_:
				self.trades[addr]['yes'] += (dir_*n)
			else:
				self.trades[addr]['no'] += (dir_*n)
		else:
			self.trades[addr] = {}
			if typ_:
				self.trades[addr]['yes'] = (dir_*n)
				self.trades[addr]['no'] = 0
			else:
				self.trades[addr]['yes'] = 0
				self.trades[addr]['no'] = (dir_*n)

	def addLiquidity(self, addr, c, r=None):
		# no liquidity has been added yet
		if (self.noShares == 0) or (self.yesShares == 0):
			y, n, r_y, r_n, ls = calcLiquidity(c, r)
		else:
			y, n, r_y, r_n, ls = calcLiquidity(c, self.getRate())
		self.lps[addr] = ls
		self.noShares += n
		self.yesShares += y

		if r_y:
			self.addTrade(addr, True, 1, r_y)
			self.yesResidShares += r_y
		elif r_n:
			self.addTrade(addr, False, 1, r_n)
			self.noResidShares += r_n

		self.stable += c

	def removeLiquidity(self, addr, nShares):
		# need enough liq shares
		assert(self.lps[addr] >= nShares)

		# create market positions from shares
		totLiqShares = sum(self.lps.values())
		px = self.getRate()
		yesShares = self.yesShares * nShares / totLiqShares
		noShares = self.noShares * nShares / totLiqShares

		self.addTrade(addr, True, 1, yesShares)
		self.addTrade(addr, False, 1, noShares)

		self.yesShares -= yesShares
		self.noShares -= noShares
		self.liqFees[addr] -= nShares / self.lps[addr] * self.liqFees[addr]
		self.lps[addr] -= nShares

		# remove from amm
		if self.lps[addr] == 0:
			del self.lps[addr]
			del self.liqFees[addr]

	def mergeShares(self, addr, nShares):
		# pct is amt of mergeable set to merge for stablecoins
		yesShares = self.trades[addr]['yes']
		noShares = self.trades[addr]['no']
		assert((yesShares >= nShares) and (noShares >= nShares))

		self.trades[addr]['yes'] -= nShares
		self.trades[addr]['no'] -= nShares

		if ((self.trades[addr]['yes'] < 0.00000001) and (self.trades[addr]['no'] < 0.00000001)):
			del self.trades[addr]

		self.stable -= nShares

	def buyShares(self, addr, typ_, c, isForSell=False):

		# for now, don't tax sales
		if not isForSell:
			liqFee = LIQ_FEE * c
			c -= liqFee
			self.distLiqFee(liqFee)

		noShares = self.noShares
		yesShares = self.yesShares
		prod = noShares*yesShares
		if typ_:
			d = yesShares+c-prod/(noShares+c)
			d = round(d) if isForSell else d
			yesShares += (c-d)
			noShares += c
		else:
			d = noShares+c-prod/(yesShares+c)
			d = round(d) if isForSell else d
			yesShares += c
			noShares += (c-d)
		self.yesShares = yesShares
		self.noShares = noShares
		px = c / d
		print("Price:",px)
		self.addTrade(addr, typ_, 1, d)
		self.stable += c

	# TODO: put an exception so doesnt fail silently
	def sellShares(self, addr, typ_, nShares):
		# first you need to buy the other share
		# then you merge, so the merge cancels the buy and net is the sale of contract
		# calculate dollar amt needed for purchase of other
		# check if we have shares to sell
		if addr in self.trades:
			if self.trades[addr][('yes' if typ_ else 'no')] > nShares:
				#import pdb; pdb.set_trace()
				d = 0
				yesShares = self.yesShares
				noShares = self.noShares
				if typ_:
					# selling yes, buying no
					d = ((nShares-yesShares-noShares)+((yesShares+noShares-nShares)**2+4*nShares*yesShares)**(0.5)) / 2
				else:
					# selling no, buying yes
					d = ((nShares-yesShares-noShares)+((yesShares+noShares-nShares)**2+4*nShares*noShares)**(0.5)) / 2
				# we don't add because we're doing this trade under the hood
				# user accrues a $d debit that is covered by merge strictly
				self.buyShares(addr, not typ_, d, isForSell=True)
				self.mergeShares(addr, nShares)


def main():

	#what happens when there is no liquidity?
	# prices?

	# trading simulation
	m = CPMM()
	initLiq = 5000
	m.addLiquidity("liqBot", initLiq, 0.65)

	addresses = ['a','b','c','d','e','f','g','h','i','j']
	sizes = [50,100,200,500,1000]
	pos = [True, False]
	direction = [1,-1]

	n = 10000
	for _ in range(n):
		addr = random.choice(addresses)
		size = random.choice(sizes)
		position = random.choice(pos)
		dir_ = random.choice(direction)
		if dir_ == 1:
			m.buyShares(addr, position, size)
		else:
			m.sellShares(addr, position, size)


if __name__ == '__main__':
	main()

