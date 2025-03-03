#!/usr/bin/python
# -*- coding: utf-8 -*-

""" **************************************************************************
	python ontofetch.py [owl ontology file path or URL]
	Ontology term fetch to tabular or json output
 
 	Author: Damion Dooley

	Ontology() class __main__() reads in given ontology file via path or 
	URL and imports all ontology class terms, including labels, 
	definitions, synonyms, deprecated status, and replacement term if
	any.  Output is produced as json or tabular tsv.

	RDFLib: This script requires python module RDFLib. RDFLib sparql 
	ISSUE: Doing a "BINDING (?x as ?y)" expression prevents ?x from 
	being output in a SELECT. bug leads to no such field being output.

	EXAMPLES
	Retrieve local file genepio-merged.owl and write files genepio-merged.json, genepio-merged.tsv into folder program was launched in.

		> python ontofetch.py ../genepio/src/ontology/genepio-merged.owl
	     
	Retrieve OBI and write files test/obi.json and test/obi.tsv into test/ subfolder.

		> python ontofetch.py https://raw.githubusercontent.com/obi-ontology/obi/master/obi.owl -o test/
	     
	Retrieve OBI "data visualization" and IAO "documenting" branches

		> python ontofetch.py https://raw.githubusercontent.com/obi-ontology/obi/master/obi.owl -o test/ -r http://purl.obolibrary.org/obo/OBI_0200111,http://purl.obolibrary.org/obo/IAO_0000572

	FUTURE: Get ontology version, and add to "version" field
	
	**************************************************************************
""" 

import json
import sys
import os
import optparse

#from ontohelper import OntoHelper as oh
import lexmapr.ontohelper as oh

import rdflib
from rdflib.plugins.sparql import prepareQuery

# Do this, otherwise a warning appears on stdout: No handlers could be 
#found for logger "rdflib.term"
import logging; logging.basicConfig(level=logging.ERROR) 

try: #Python 2.7
	from collections import OrderedDict
except ImportError: # Python 2.6
	from ordereddict import OrderedDict

def stop_err(msg, exit_code = 1):
	sys.stderr.write("%s\n" % msg)
	sys.exit(exit_code)

class MyParser(optparse.OptionParser):
	"""
	Allows formatted help info.  From http://stackoverflow.com/questions/1857346/python-optparse-how-to-include-additional-info-in-usage-output.
	"""
	def format_epilog(self, formatter):
		return self.epilog


class Ontology(object):
	"""


	"""

	CODE_VERSION = '0.0.4'
	# This list doesn't include synonym types. ontohelper.py provides them.
	FIELDS = ['id','parent_id','language','ontology','other_parents','label','definition','ul_label','ui_definition','ui_help','deprecated','replaced_by']


	def __init__(self):

		self.onto_helper = oh.OntoHelper()
		# ADDITIONAL FIELDS THAT WOULD BE MANAGED IN SYNCHRONIZATION of TARGET
		# LOOKUP TABLE: 'updated','preferred'
		self.fields = self.FIELDS + self.onto_helper.SYNONYM_FIELDS

		""" 
		Add these PREFIXES to Sparql query window if you want to test a query there:

		PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> PREFIX owl: <http://www.w3.org/2002/07/owl#>
		PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX OBO: <http://purl.obolibrary.org/obo/>
		PREFIX xmls: <http://www.w3.org/2001/XMLSchema#>
		""" 
	 
		self.queries = {
			##################################################################
			# Generic TREE "is a" hierarchy from given root.
			#
			'tree': prepareQuery("""
				PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
				SELECT DISTINCT ?id ?label ?parent_id ?deprecated ?replaced_by 
				WHERE {	
					?parent_id rdfs:subClassOf* ?root.
					?id rdfs:subClassOf ?parent_id.
					OPTIONAL {?id rdfs:label ?label}.
	 				OPTIONAL {?id GENEPIO:0000006 ?ui_label}. # for ordering
					OPTIONAL {?id owl:deprecated ?deprecatedAnnot.
						BIND(xsd:string(?deprecatedAnnot) As ?deprecated).
					}.
					OPTIONAL {?id IAO:0100001 ?replaced_byAnnot.
						BIND(xsd:string(?replaced_byAnnot) As ?replaced_by).
					}.	
				}
				ORDER BY ?parent_id ?ui_label ?label 
			""", initNs = self.onto_helper.namespace),


			# ################################################################
			# UI LABELS 
			# These are annotations directly on an entity.  This is the only place
			# that ui_label and ui_definition should really operate. Every entity
			# in OWL file is retrieved for their rdfs:label, IAO definition etc.
			# FUTURE: ADD SORTING OPTIONS, CUSTOM ORDER.
			'entity_text': prepareQuery("""

				SELECT DISTINCT ?label ?definition ?ui_label ?ui_definition
				WHERE {  
					{?datum rdf:type owl:Class} 
					UNION {?datum rdf:type owl:NamedIndividual} 
					UNION {?datum rdf:type rdf:Description}.
					OPTIONAL {?datum rdfs:label ?label.} 
					OPTIONAL {?datum IAO:0000115 ?definition.}
					OPTIONAL {?datum GENEPIO:0000006 ?ui_label.} 
					OPTIONAL {?datum GENEPIO:0000162 ?ui_definition.}
				} ORDER BY ?label
			""", initNs = self.onto_helper.namespace),




			# ################################################################
			# Fetch parent IDs of given entity. with respect to class-subclass
			# relations.
			# STATUS: UNTESTED, UNUSED
			# INPUT
			# 	?datum_id : id of term to get parents for
			# OUTPUT
			#   ?parent_ids
			#
			#'entity_parents': prepareQuery("""
			#	SELECT DISTINCT ?datum_id (group_concat(distinct ?parent_id;separator=",") as ?parent_ids)
			#	WHERE {
			#		?datum_id rdfs:subClassOf ?parent_id.
			#		?parent_id rdfs:label ?label # to ensure parent_id entity is in graph as well.
			#	}
			#""", initNs = self.onto_helper.namespace),
		}

	def __main__(self):
		"""
		By default, retrieves 'http://www.w3.org/2002/07/owl#Thing' and all
		subclasses in given ontology and place them into self.onto_helper.struct.specifications.  Produces a .json and .tsv
		output file of all term labels, definitions, synonyms, etc.

		To retrieve a 
		branch like BFO:entity (BFO:0000001), add command line option:
		 -r http://purl.obolibrary.org/obo/BFO_0000001  
		
		INPUT
			args[0]:string: A filepath or URL of ontology to process
			options.root_uri: string: A comma-delimited list of 0 or more term URI ids.
		"""

		(options, args) = self.get_command_line()

		if options.code_version:
			print (self.CODE_VERSION)
			return self.CODE_VERSION

		if not len(args):
			stop_err('Please supply an OWL ontology file (in RDF/XML format)')

		(main_ontology_file, output_file_basename) = self.onto_helper.check_ont_file(args[0], options)

		# Load main ontology file into RDF graph
		print ("Fetching and parsing " + main_ontology_file + " ...")

		try:
			# ISSUE: ontology file taken in as ascii; rdflib doesn't accept
			# utf-8 characters so can experience conversion issues in string
			# conversion stuff like .replace() below
			self.onto_helper.graph.parse(main_ontology_file, format='xml')

		except Exception as e:
			#urllib2.URLError: <urlopen error [Errno 8] nodename nor servname provided, or not known>
			stop_err('WARNING:' + main_ontology_file + " could not be loaded!\n", e)

		# Add each ontology include file (must be in OWL RDF format)
		self.onto_helper.do_ontology_includes(main_ontology_file)

		# Load self.struct with ontology metadata
		self.onto_helper.set_ontology_metadata(self.onto_helper.queries['ontology_metadata'])
		print ('Metadata: ' + json.dumps(self.onto_helper.struct['metadata'],  sort_keys=False, indent=4, separators=(',', ': ')) )

		for term_id in options.root_uri.split(','):
			print ('Doing term hierarchy query starting at: ' + term_id)
			specBinding = {'root': rdflib.URIRef(term_id)} 
			entities = self.onto_helper.do_query_table(self.queries['tree'], specBinding)

			print ('Doing terms: ' + str(len(entities)) )
			self.do_entities(entities)
		
		self.onto_helper.do_output_json(self.onto_helper.struct, output_file_basename)
		self.onto_helper.do_output_tsv(self.onto_helper.struct, output_file_basename, self.fields)


	def do_entities(self, table):
		""" 
			Converts table of ontology terms - each having its own row of
			dictionary, into self.struct['specifications'] dictionary.
			References to parents are also pursued - on a second iteration
			so that they are primarily filled in on first pass if already
			mentioned in hierarchy, but barebones record is created for
			them if not.

			Example output of one term conversion:
				"GENEPIO:0001677": {
		            "id": "GENEPIO:0001677",
		            "parent": "GENEPIO:0001606",
		            "ui_label": "contact specification - patient"
		            }
		        }

			
		"""

		# List of parents to process after 1st pass through table's entities.
		parents = [] 

		for myDict in table:
			self.do_entity(myDict)

			parent_id = self.onto_helper.get_parent_id(myDict) 
			if parent_id:
				if not parent_id in parents:
					parents.append(parent_id)

		# 2nd pass does parents:
		# Parent gets entry in structure too, though maybe not a label.
		# If not already mentioned in its own right, then it was parent
		# of top-level entity, and not really important, so it gets a
		# minimal entry.
		for parent_id in parents:
			if not parent_id in self.onto_helper.struct['specifications']:
				self.onto_helper.set_entity_default(self.onto_helper.struct, 'specifications', parent_id, {
					'id': parent_id, 
					'datatype': 'entity'
				})


	def do_entity(self, myDict):
		"""
		Inserts or overlays entity described by myDict into 
		self.struct['specifications']
		
		INPUT
			myDict:dict (row from table)
			prefix:string indicates source ontology for term
		OUTPUT
			myDict:dict modified entity
		"""

		id = str(myDict['id'])
		myDict['id'] = id
		# So far terms are not distinguished by any associated 
		# categorical, string or numeric datatype
		# myDict['datatype'] = 'entity'

		if 'prefix' in self.onto_helper.struct['metadata']:
			myDict['ontology'] = self.onto_helper.struct['metadata']['prefix']

		if 'replaced_by' in myDict:
			myDict['replaced_by'] = self.onto_helper.get_entity_id(myDict['replaced_by'])

		# Addresses case where a term is in query more than once, as
		# a result of being positioned in different places in hierarchy.
		if id in self.onto_helper.struct['specifications']:
			existing = self.onto_helper.struct['specifications'][id]
			parent_id = myDict['parent_id']
			existing_p_id = existing['parent_id']
			if parent_id and existing_p_id and parent_id != existing_p_id:
				if not 'other_parents' in existing:
					existing['other_parents'] = []
				existing['other_parents'].append(parent_id)

		self.onto_helper.set_entity_default(self.onto_helper.struct, 'specifications', id, myDict)

		self.do_entity_text(id)
		self.do_entity_synonyms(id)


	def do_entity_text(self, id):
		"""
		For given entity, all 'labels' query fields are returned (rdfs:label, IAO 
		definition, UI label, UI definition) and added to the entity directly.

		"""
		myURI = rdflib.URIRef(self.onto_helper.get_expanded_id(id))
		rows = self.onto_helper.graph.query(
			self.queries['entity_text'],	
			initBindings = {'datum': myURI} 
		)
		# Should only be 1 row to loop through
		for row in rows: 
			myDict = row.asdict()	
			# Adds any new text items to given id's structure
			self.onto_helper.struct['specifications'][id].update(myDict) 
			# Issue: carriage returns in definition; this is taken care of in
			# do_output_tsv()


	def do_entity_synonyms(self, id):
		"""
		Augment each entry in 'specifications' with semi-colon-delimited 
		synonyms gathered from 'entity_synonyms' query of annotations which
		originate in these relations 

			oboInOwl:hasSynonym
			oboInOwl:hasBroadSynonym
			oboInOwl:hasExactSynonym
			oboInOwl:hasNarrowSynonym
			IAO:0000118 alternative_term

		ISSUE: 
		Not Multilingual yet.  Some synonym entries have {language: french} or
		{language: Scottish Gaelic} etc. at end. Add @en , @fr etc. to end of 
		phrase.

		INPUT
			?synonym ?broad_synonym ?exact_synonym ?narrow_synonym ?alternative_term
		OUTPUT
			for each of above fields, an array containing one or more terms
		"""
		
		myURI = rdflib.URIRef(self.onto_helper.get_expanded_id(id))
		rows = self.onto_helper.graph.query(
			self.onto_helper.queries['entity_synonyms'], 
			initBindings = {'datum': myURI }
		)

		spec = self.onto_helper.struct['specifications'][id]

		for row in rows:

			# Specification distinguishes between these kinds of synonym
			for field in self.onto_helper.SYNONYM_FIELDS:

				if row[field]: 
					# Clean up synonym phrases.  Can't split comma-delimited synonyms
					# because a number of ontologies have phrase synonyms with commas
					# in them.  Also chemistry expressions have tight (no space)
					# comma separated synonyms
					phrases = row[field].replace('\\n', ';').strip().replace('"','').split(';')
					if phrases:
						prefix_field = field.replace('_',':',1)
						if prefix_field in spec:
							spec[prefix_field] += phrases
						else:
							spec[prefix_field] = phrases


	def get_command_line(self):
		"""
		*************************** Parse Command Line *****************************
		"""
		parser = MyParser(
			description = 'Ontology term fetch to tabular output.  See https://github.com/GenEpiO/genepio',
			usage = 'ontofetch.py [ontology file path or URL] [options]*',
			epilog="""  """)
		
		# first (unnamed) parameter is input file or URL
		# output to stdio unless -o provided in which case its to a file.

		# Standard code version identifier.
		parser.add_option('-v', '--version', dest='code_version', default=False, action='store_true', help='Return version of this code.')

		parser.add_option('-o', '--output', dest='output_folder', type='string', help='Path of output file to create')
		
		parser.add_option('-r', '--root', dest='root_uri', type='string', help='Comma separated list of full URI root entity ids to fetch underlying terms from. Defaults to owl#Thing.', default='http://www.w3.org/2002/07/owl#Thing')

		return parser.parse_args()


if __name__ == '__main__':

	genepio = Ontology()
	genepio.__main__()  

