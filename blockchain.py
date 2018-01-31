import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request

class Blockchain(object):
	"""docstring for Blockchain"""

	def __init__( self ):
		self.chain = []
		self.c_transactions = []
		self.nodes = set()

		self.add_new_block( previous_hash='1', proof=100 )


	def add_new_block( self, proof, previous_hash ):
		
		block = {
			"index": len(self.chain) + 1,
			"timestamp": time(),
			"transactions": self.c_transactions,
			"proof": proof,
			"previous_hash": previous_hash or self.hash( self.chain[-1] ),
		}

		self.c_transactions = []
		self.chain.append( block )

		return block


	def add_new_transactions( self, sender, recipient, value ):
		
		self.c_transactions.append({
			"sender": sender,
			"recipient": recipient,
			"value": value
		})

		return self.last_block['index'] + 1


	@staticmethod
	def hash( block ):
		block_as_string = json.dumps(block, sort_keys=True).encode()
		return hashlib.sha256( block_as_string ).hexdigest()


	@property
	def last_block( self ):
		return self.chain[-1]

	def proof_of_work( self, last_proof ):
		proof = 0
		while self.is_valid_proof(last_proof, proof) is False:
			proof += 1

		return proof

	@staticmethod
	def is_valid_proof( last_proof, proof ):
		guess = f'{last_proof}{proof}'.encode()
		guess_h = hashlib.sha256(guess).hexdigest()

		return guess_h[:4] == "0000"


	def register_node( self, address ):
		parsed_url = urlparse( address )
		self.nodes.add( parsed_url.netloc )


	def is_valid_chain( self, chain ):
		last_block = chain[0]
		current_index = 1

		while current_index < len(chain):
			block = chain[current_index]
			print(f'{last_block}')
			print(f'{block}')
			print("\n-----------\n")

			if block['previous_hash'] != self.hash( last_block ):
				return False

			if not self.is_valid_proof( last_block['proof'], block['proof'] ):
				return False

			last_block = block
			current_index += 1

		return True


	def resolve_conflicts( self ):
		neighbours = self.nodes
		new_chain = None
		max_length = len( self.chain )

		for node in neighbours:
			response = requests.get(f'http://{node}/chain')

			if response.status_code == 200:
				length = response.json()['length']
				chain = response.json()['chain']

				if length > max_length and self.is_valid_chain( chain ):
					max_length = length
					new_chain = chain


		if new_chain:
			self.chain = new_chain
			return True

		return False



application = Flask( __name__ )
node_identifier = str(uuid4()).replace( '-', '' )
blockchain = Blockchain();

@application.route( '/', methods=['GET'] )
def index():
	return 'You can use the following routes: /mine, /transaction/new, /chain, /node/register, /node/resolve'

@application.route( '/mine', methods=['GET'] )
def mine():
	last_block = blockchain.last_block
	last_proof = last_block['proof']

	proof = blockchain.proof_of_work( last_proof )

	blockchain.add_new_transactions(
		sender = "0",
		recipient = node_identifier,
		value = 1,
	)

	previous_hash = blockchain.hash( last_block )
	block = blockchain.add_new_block( proof, previous_hash )


	resp = {
		"message": "Forged new block",
		"index": block['index'],
		"transactions": block['transactions'],
		"proof": block['proof'],
		"previous_hash": block['previous_hash'],
	}

	return jsonify( resp ), 200

@application.route( '/transaction/new', methods=['POST'] )
def transaction_new():
	get_values = request.get_json()

	required_values = ['sender', 'recipient', 'value']
	if not all (k in get_values for k in required_values):
		return "Missing required values. Please try again", 400

	index = blockchain.add_new_transactions( get_values['sender'], get_values['recipient'], get_values['value'] )

	resp = {
		"messages": f'Your transaction will be added to Block {index}'
	}

	return jsonify( resp ), 201

@application.route( '/chain', methods=['GET'] )
def get_chain():
	resp = {
		"chain": blockchain.chain,
		'length': len( blockchain.chain ),
	}

	return jsonify( resp ), 200

@application.route( '/node/register', methods=['POST'] )
def node_register():
	get_values = request.get_json()

	nodes = get_values.get('nodes')

	if nodes is None:
		resp = {
			"error": "Please post valid list",
		}

		return jsonify( resp ), 400

	for node in nodes:
		blockchain.register_node( node )

		resp = {
			"message": "New nodes have been added",
			"total_nodes": list( blockchain.nodes ),
		}
		return jsonify( resp ), 201

@application.route( '/node/resolve', methods=['GET'] )
def node_resolve():
	action = blockchain.resolve_conflicts()

	if action:
		resp = {
			"message": "Our chain was replaced",
			"new_chain": blockchain.chain
		}
	else:
		resp = {
			'message': "Our chain is authoritative",
			'chain': blockchain.chain
		}

	return jsonify( resp ), 200


if __name__ == '__main__':
	from argparse import ArgumentParser

	parser = ArgumentParser()
	parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
	args = parser.parse_args()
	port = args.port

	application.run(host='127.0.0.1', port=port)
