from readBNGXML import parseXML
import networkx as nx
import argparse
import sys
sys.path.insert(0, './SBMLparser')
from rulifier import componentGroups


def extractMolecules(action, site1, site2, chemicalArray):
    '''
    this method goes through the chemicals in a given array 'chemicalArray'
    and extracts its atomic patterns into two arrays:
        those elements that are contained in [site1,site2] will be put in the
        reactionCenter set. The rest will    be placed in the context set.
        The entire system will be put into the atomicPatterns dictionary
    Keyword arguments:
    site1,site2 -- where the action takes place
    chemicalArray -- the list of species we will be extracting atomic patters
    from
    '''
    atomicPatterns = {}
    reactionCenter = set()
    context = set()

    for reactant in chemicalArray:
        ta, tr, tc = reactant.extractAtomicPatterns(action, site1, site2)
        #for element in ta:
        #    atomicPatterns.add(element)
        atomicPatterns.update(ta)
        for element in tr:
            reactionCenter.add(element)
        for element in tc:
            context.add(element)

    return atomicPatterns, reactionCenter, context


def getMapping(mapp, site):
    for mapping in mapp:
        if site in mapping:
            return [x for x in mapping if x != site][0]


def solveWildcards(atomicArray):
    '''
    When you have a wildcard '+' as a bond configuration, this method allows you
    to go through the list of atomic elements and find which patterns the '+'
    can potentially resolve to
    '''
    standinArray = {}
    for wildcard in [x for x in atomicArray if '+' in x]:
        for atomic in [x for x in atomicArray if '+' not in x and len(atomicArray[x].molecules) > 1]:
            if atomicArray[wildcard].molecules[0].name in [x.name for x in atomicArray[atomic].molecules]:
                if wildcard not in standinArray:
                    standinArray[wildcard] = []
                standinArray[wildcard].append(atomicArray[atomic])
    atomicArray.update(standinArray)


def extractSingleTransformation(rule):
    '''
    goes through a rule and extracts its reactioncenter,context and product
    atomic patterns per transformation action
    '''
    atomicArray = {}
    transformationCenter = []
    transformationContext = []
    productElements = []
    actionName = []
    index = 0
    label = []
    act = rule.actions
    react = rule.reactants
    mapp = rule.mapping
    product = rule.products
    index += 1
    for action in act:
        atomic, reactionCenter, context = extractMolecules(action.action, action.site1,
                                                           action.site2, react)
        transformationCenter.append(reactionCenter)
        transformationContext.append(context)
        atomicArray.update(atomic)
        productSites = [getMapping(mapp, action.site1),
                        getMapping(mapp, action.site2)]
        atomic, rc, _ = extractMolecules(action.action, productSites[0], productSites[1],
                                         product)
        productElements.append(rc)
        atomicArray.update(atomic)
        actionName.append('%i-%s' % (index, action.action))
        r = '+'.join([str(x) for x in react])
        p = '+'.join([str(x) for x in product])
        label.append('->'.join([r, p, '%i-%s' % (index, action.action)]))

    solveWildcards(atomicArray)

    return atomicArray, transformationCenter, transformationContext, productElements, actionName, label


def testForIntersection(mutualExclusion, mutualExclusionList, mutualExclusionDictionary):
    for exclusion in mutualExclusionDictionary:
        pivot = None
        if mutualExclusion[0] in exclusion:
            pivot = mutualExclusion[1]
        elif mutualExclusion[1] in exclusion:
            pivot = mutualExclusion[0]
        if pivot:
            exclusionCopy = exclusion[:]
            otherExclusionList = []
            for exclusionCandidate in mutualExclusionList:
                if pivot in exclusionCandidate:
                    otherChemical = [x for x in exclusionCandidate if x != pivot][0]
                    if otherChemical in exclusionCopy:
                        exclusionCopy.remove(otherChemical)
                        otherExclusionList.append(exclusionCandidate)
            if len(exclusionCopy) == 0:
                exclusion.append(pivot)
                return otherExclusionList
                
    return False


def processExtendedInformation(extendedInformation):

    mutualExclusionDictionary = {}
    for molecule in extendedInformation:
        tmpmutualExclusion = []
        idx = 0
        exclusionList = list(extendedInformation[molecule]['mutualExclusion'])
        while idx < len(exclusionList):
            intersection = testForIntersection(list(exclusionList[idx]), exclusionList, tmpmutualExclusion)
            if not intersection:
                tmpmutualExclusion.append(list(exclusionList[idx]))
                exclusionList.remove(exclusionList[idx])
                idx = 0
            else:
                for individualIntersection in intersection:
                    exclusionList.remove(individualIntersection)
                    idx = 0
        mutualExclusionDictionary[molecule] = tmpmutualExclusion
    return mutualExclusionDictionary


def getDummyNode(bondpartner1, bondpartner2, collapsedComponents):
    if bondpartner1 in collapsedComponents:
        for collapsedcomponent in collapsedComponents[bondpartner1]:
            if bondpartner2.lower() in collapsedcomponent:
                return '/'.join(collapsedcomponent), '{0}({1})'.format(bondpartner1, '/'.join(collapsedcomponent)), "#FFDDDD"

    return '_'.join([bondpartner1, bondpartner2]), bondpartner2.lower(), "#FFFFFF"



def getCounter():
    if not hasattr(getCounter, 'counter'):
        getCounter.counter = 0
        

    getCounter.counter += 1
    return getCounter.counter


def createCollapsedContact(rules, species, transformations, fileName, extendedInformation, contextOnlyFlag):
    '''
    creates a collapsed bipartite graph given a list of rules
    collapsed bipartite means that molecules are represented as structureless nodes and

    Args:
        rules: The list of rules to process
        transformations: which transformations do we want to process (their index)
        fileName: output filename
        reactioncenter,context,products: booleans indicating whether we desire include the reactioncenter,context
    or product in our ouput file
    '''

    def createNode(graph, name,  graphicsDict,  labelGraphicsDict,isGroup,gid):
        idNumber = getCounter()

        if contextOnlyFlag:
            if isGroup:
                graph.add_node(name, graphics=graphicsDict, LabelGraphics=labelGraphicsDict,isGroup=isGroup,id=idNumber)
            else:
                graph.add_node(name, graphics=graphicsDict, LabelGraphics=labelGraphicsDict,gid=gid,id=idNumber)
        else:
            graph.add_node(name, graphics=graphicsDict,LabelGraphics=labelGraphicsDict, id=idNumber)

    graph = nx.DiGraph()
    processNodes = []
    counter = 1
    for speciesUnit in species:
        createNode(graph, speciesUnit.name, {'type': 'roundrectangle', 'fill': '#FFCC00'},{}, 1,0)

        
    mainidx = 0
    speciesName = [x.name for x in species]
    collapsedComponents = processExtendedInformation(extendedInformation)
    for rule, _, _, _ in rules:
        mainidx += 1
        nonatomicset = False
        activeReactants = [y.name for x in rule.reactants for y in x.molecules]
        activeProducts = [y.name for x in rule.products for y in x.molecules]

        atomicArray, transformationCenter, transformationContext, productElements, actionName, label = extractSingleTransformation(rule)

        for idx in range(len(rule.actions)):
            if rule.actions[idx].action in ['Add', 'Delete']:
                nonatomicset = True
            elif rule.actions[idx].action in ['AddBond']:

                bondpartners = [x.split('(')[0] for x in transformationCenter[idx]]

                if len(bondpartners) == 2:
                    dummyNode, label1, fill1 = getDummyNode(bondpartners[0], bondpartners[1], collapsedComponents)
                    dummyNode2, label2, fill2 = getDummyNode(bondpartners[1], bondpartners[0], collapsedComponents)
                    createNode(graph, dummyNode, {'type': "circle", 'fill': fill1}, {'text': label1}, 0, graph.node[bondpartners[0]]['id'])
                    createNode(graph, dummyNode2, {'type': "circle", 'fill': fill2}, {'text': label2}, 0, graph.node[bondpartners[1]]['id'])

                    if not contextOnlyFlag:
                        if (dummyNode, bondpartners[0]) not in graph.edges():
                            graph.add_edge(bondpartners[0], dummyNode, graphics={'fill': "#000000", 'width': 3}, weight=1)
                        if (dummyNode2, dummyNode) not in graph.edges():
                            graph.add_edge(dummyNode, dummyNode2, graphics={'fill': "#000000"}, weight=1)
                        if (dummyNode2, bondpartners[1]) not in graph.edges():
                            graph.add_edge(bondpartners[1], dummyNode2, graphics={'fill': "#000000", 'width': 3}, weight=1)


                elif len(bondpartners) == 1:
                    dummyNode = '{0}_{0}'.format(bondpartners[0])
                    createNode(graph, dummyNode, {'type': "circle", 'fill': "#FFFFFF"}, {'text': bondpartners[0]}, 0,graph.node[bondpartners[0]]['id'])
                    if not contextOnlyFlag:
                        graph.add_edge(bondpartners[0], dummyNode, graphics={'fill': "#000000"}, weight=1)
                        graph.add_edge(dummyNode, bondpartners[0], graphics={'fill': "#000000"}, weight=1)

                else:
                    nonatomicset = True
                for x in bondpartners:
                    if x in activeReactants:
                        activeReactants.remove(x)
                    if x in activeProducts:
                        activeProducts.remove(x)
            elif rule.actions[idx].action in ['StateChange']:
                molecule = [x.split('(')[0] for x in transformationCenter[idx]]
                state = [x.split('(')[1].split('~')[0] for x in transformationCenter[idx]]

                createNode(graph, molecule[0] + '_' + state[0], {'type': "circle", 'fill': "#CCFFCC"}, {'text': state[0]}, 0, graph.node[molecule[0]]['id'])
                if not contextOnlyFlag:
                    graph.add_edge(molecule[0] + '_' + state[0], molecule[0], graphics={'fill': "#000000"}, weight=0.7)

                processNodes.append(state[0])
                if molecule[0] in activeReactants:
                    activeReactants.remove(molecule[0])
                if molecule[0] in activeProducts:
                    activeProducts.remove(molecule[0])
        # deal with add/delete information
        nonatomicset = False
        if nonatomicset:
            graph.add_node(mainidx, graphics={'type': "hexagon"})
            processNodes.append(mainidx)
            for element in activeReactants:
                if element not in graph.node:
                    graph.add_node(element, graphics={'type': 'roundrectangle', 'fill': '#FFCC00'})
                graph.add_edge(element, mainidx, graphics={'targetArrow': "standard"})
            for element in activeProducts:
                graph.add_edge(mainidx, element)

    color = {'requirement': '#0000FF', 'exclusion': '#FF0000', 'mutualExclusion': '#FF0000'}

    # deal with information in extendedInformation
    for molecule in extendedInformation:
        for relationship in extendedInformation[molecule]:
            for requirement in extendedInformation[molecule][relationship]:
                if relationship == 'mutualExclusion':
                    requirement1 = list(requirement)[0]
                    requirement2 = list(requirement)[1]
                elif relationship in ['nullexclusion', 'independent', 'nullrequirement']:
                    continue
                else:
                    requirement1 = requirement[0][0]
                    requirement2 = requirement[1][0]

                index1 = [i for i, x in enumerate(speciesName) if x.lower() == requirement1]
                index2 = [i for i, x in enumerate(speciesName) if x.lower() == requirement2]
                node1 = 1 if len(index1) > 0 else '{0}_{1}'.format(molecule, requirement1)
                node2 = 1 if len(index2) > 0 else '{0}_{1}'.format(molecule, requirement2)
                if node1 == 1:
                    node1, label1, fill1 = getDummyNode(molecule, speciesName[index1[0]], collapsedComponents)
                if node2 == 1:
                    node2, label2, fill2 = getDummyNode(molecule, speciesName[index2[0]], collapsedComponents)
                if relationship != 'mutualExclusion':
                    #pass
                    #print node1,node2

                    if node1 not in graph.nodes():
                        createNode(graph, node1, {'type': "circle", 'fill': fill1}, {'text': label1}, 0, graph.node[molecule]['id'])
                        if not contextOnlyFlag:
                            graph.add_edge(molecule, node1, graphics={'fill': "#000000", 'width': 3}, weight=1)
                        node1m, label1m, fill1m = getDummyNode(speciesName[index1[0]], molecule, collapsedComponents)
                        if 'mod' not in label1m:
                            if node1m not in graph.nodes():
                                createNode(graph, node1m, {'type': "circle", 'fill': fill1m}, {'text': label1m}, 0, graph.node[speciesName[index1[0]]]['id'])
                                if not contextOnlyFlag:
                                    if node1m not in graph.nodes():
                                        graph.add_edge(speciesName[index1[0]], node1m, graphics={'fill': "#000000", 'width': 3}, weight=1)
                                    graph.add_edge(node1, node1m, graphics={'fill': "#000000"}, weight=1)
    
                    if node2 not in graph.nodes():
                        createNode(graph, node2, {'type': "circle", 'fill': fill2}, {'text': label2}, 0, graph.node[molecule]['id'])
                        if not contextOnlyFlag:
                            graph.add_edge(molecule, node2, graphics={'fill': "#000000", 'width': 3}, weight=1)
                        node2m, label2m, fill2m = getDummyNode(speciesName[index1[0]], molecule, collapsedComponents)
                        if 'mod' not in label2m:
                            if node2m not in graph.nodes():
                                createNode(graph, node2m, {'type': "circle", 'fill': fill2m}, {'text': label2m}, 0, graph.node[speciesName[index1[0]]]['id'])
                                if not contextOnlyFlag:
                                    if node2m not in graph.nodes():
                                        graph.add_edge(speciesName[index1[0]], node2m, graphics={'fill': "#000000", 'width': 3}, weight=1)
                                    graph.add_edge(node2, node2m, graphics={'fill': "#000000"}, weight=1)



                    graph.add_edge(node1, node2, graphics={'fill': color[relationship], 'style': "dashed", 'targetArrow': "standard"}, weight=0.1)
                else:
                    #if relationship == 'exclusion':
                    pass
                    #graph.add_edge(node1,node2,graphics={'fill':color[relationship],'style':"dashed"},weight=0.1)


    #layout nx.spring_layout(graph)
    #for element in graph.nodes():

    nx.write_gml(graph, fileName)


def defineConsole():
    parser = argparse.ArgumentParser(description='SBML to BNGL translator')
    parser.add_argument('-i', '--input', type=str, help='settings file',required=True)
    parser.add_argument('-o', '--output', type=str, help='output directory')
    parser.add_argument('-c', '--context-only',action='store_true')
    parser.add_argument('-r', '--rulify', action='store_true')
    return parser    


def main(fileName,outputfilename,extendedInformation,contextOnlyFlag):
    molecules,rules,_ = parseXML(fileName)
    createCollapsedContact(rules,molecules,[1],outputfilename,extendedInformation,contextOnlyFlag)         


if __name__ == "__main__":
    parser = defineConsole()
    namespace = parser.parse_args()
    inputFile = namespace.input
    if namespace.output != None:
        outputFile = namespace.output
    else:
        outputFile = inputFile + '.gml'
    if namespace.rulify:
        extendedInformation = componentGroups.getContextRequirements(inputFile)   
    else:
        extendedInformation = {}
    main(inputFile,outputFile,extendedInformation, namespace.context_only)
    
    #addAnnotations('fceri_ji')