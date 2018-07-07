#!/usr/bin/env python3
import hashlib
import json
import requests
from time import time
from uuid import uuid4
from textwrap import dedent
from flask import Flask, jsonify, request

class Blockchain(object):
  def __init__(self):
    # create a genesis block with no transactions or predecessor
    self.chain = []
    self.current_transactions = []
    self.new_block(previous_hash=1, proof=100)
    self.nodes = set()

  def register_node(self, address):
    #add a new node to the list of nodes
    parsed_url = urlparse(address)
    self.nodes.add(parsed_url.netloc)

  def new_block(self, proof, previous_hash=None):
    # create a new Block, add it to the chain, and return it
    # reset the current list of transactions
    block = {
      'index': len(self.chain) + 1,
      'timestamp': time(),
      'transactions': self.current_transactions,
      'proof': proof,
      'previous_hash': previous_hash or self.hash(self.chain[-1])
    }
    self.current_transactions = []
    self.chain.append(block)
    return block

  def new_transaction(self, sender, recipient, amount):
    # push a new transaction obj into the current_transactions array
    # return the next block index, aka the one that this trancation will be added to
    self.current_transactions.append({
      'sender': sender,
      'recipient': recipient,
      'amount': amount
    })
    return self.last_block['index'] + 1

  def valid_chain(self, chain):
    # determine if a given blockchain is valid by looping through each block and verifying both the hash and proof
    last_block = chain[0]
    current_index = 1
    while current_index < len(chain):
      block = chain[current_index]
      print(f'{last_block}')
      print(f'{block}')
      print("\n-------------\n")
      # validate hash
      if block['previous_hash'] != self.hash(last_block):
        return False
      # validate proof
      if not self.valid_proof(last_block['proof'], block['proof']):
        return False
      last_block = block
      current_index += 1
    return True

    def resolve_conflicts(self):
      # Consensus algorithm that loops through all of our neighboring nodes, downloads their chains, and verifies them using the 'valid_chain()' method.  if a longer, valid chain is found, we replace ours
      neighbors = self.nodes
      new_chain = None
      max_length = len(self.chain)
      # grab and verify the chains from all the nodes in our netowrk
      for node in neighbors:
        response = requests.get(f'http://{node}/chain')
        if response.status_code == 200:
          length = response.json()['length']
          chain = response.json()['chain']
          # check if the length is longer and the chain is valid
          if length > max_length and self.valid_chain(chain):
            max_length = length
            new_chain = chain
      # replace our chain if we discovered a new, longer valid chain
      if new_chain:
        self.chain = new_chain
        return True

      return False

  @staticmethod
  def hash(block):
    # create a SHA-256 hash of a Block
    # sort the dictionary for consistent hashes
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

  @property
  def last_block(self):
    # return the last Block in the chain
    return self.chain[-1]

  def proof_of_work(self, last_proof):
    # incremement x each time valid_proof(last_proof, x=0) = false
    # return x where valid_proof(last_proof, x) = true
    proof = 0
    while self.valid_proof(last_proof, proof) is False:
      proof +=1
    return proof

  @staticmethod
  def valid_proof(last_proof, proof):
    #return x where hashlib.sha256(x) last 4 digits = 0000
    guess = f'{last_proof}{proof}'.encode()
    guess_hash = hashlib.sha256(guess).hexdigest()


# node init
app = Flask(__name__)
# generate a unique name for this node
node_identifier = str(uuid4()).replace('-','')
# blockchain init
blockchain = Blockchain()

########
# routes

@app.route('/mine', methods=['GET'])
def mine():
  # calculate the proof
  last_block = blockchain.last_block
  last_proof = last_block['proof']
  proof = blockchain.proof_of_work(last_proof)
  # reward the miner by adding a transaction granting them 1 coin
  blockchain.new_transaction(
    sender = '0',
    recipient = node_identifier,
    amount = 1
  )
  # forge the new Block by adding it to the chain
  previous_hash = blockchain.hash(last_block)
  block = blockchain.new_block(proof, previous_hash)
  response = {
    'message': 'New Block Forged',
    'index': block['index'],
    'transactions': block['transactions'],
    'proof': block['proof'],
    'previous_hash': block['previous_hash']
  }
  return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
  values = request.get_json()
  # check for all required fields
  required = ['sender', 'recipient', 'amount']
  if not all(k in values for k in required):
    return 'Missing values', 400
  #create a new transaction and return a confirmation message
  index = blockchain.new_transaction(values['sender'], values['recipient'],values['amount'])
  response = {'message': f'Transaction will be added to Block {index}'}
  return jsonify(response), 201

@app.route('/chain', methods=['GET'])
# return the full Blockchain
def full_chain():
  response = {
    'chain': blockchain.chain,
    'length': len(blockchain.chain)
  }
  return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
  values = request.get_json()
  nodes = values.get('nodes')
  if nodes is None:
    return "Error: Please supply a valid list of nodes", 400
  for node in nodes:
    blockchain.register_node(node)
  response = {
    'message': 'New nodes have been added',
    'total_nodes': list(blockchain.nodes)
  }
  return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
  replaced = blockchain.resolve_conflicts()
  if replaced:
    response = {
      'message': 'Our chain was replaced',
      'new_chain': blockchain.chain
    }
  else:
    response = {
      'message': 'Our chain is authoritative',
      'chain': blockchain.chain
    }
  return jsonify(response), 200

##################
# start the server

if __name__ == '__main__':
  # run the server
  app.run(host='0.0.0.0', port=5000)
