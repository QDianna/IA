from copy import deepcopy
import random

import argparse
import ast
import utils

class TimetableState:
    def __init__(self, data):
        self.intervals = data['Intervale']            # lista de tupluri int
        self.subjects = data['Materii']               # dictionar {denumire:nr_studenti}
        self.professors = data['Profesori']           # dictionar {nume : {constrangeri : lista, materii : lista}}
        self.days = data['Zile']                      # lista de str
        self.classrooms = data['Sali']                # dictionar {denumire : {capacitate : int, materii : lista}}

        self.professors_programs = {}                 # dictionar {nume: dictionar {zile: lista tuple intervale}}
        self.subjects_noofstudents = data['Materii']  # dictionar {denumire: numar studenti nerepartizati inca}

        self.timetable = self.generate_timetable()


    def check_hard_constraints(self, day, interval, room, subject, prof) -> bool:
        '''
        Verifica daca o repartizare profesor - materie, sala - zi, interval este valida dpdv hard constraints.
        '''
        # 1. Într-un interval orar și o sală se poate susține o singură materie de către un singur profesor - veific cand incerc pun/mut o ora
        # 2. Într-un interval orar, un profesor poate ține o singură materie, într-o singură sală
        if (prof in self.professors_programs) and day in self.professors_programs[prof] and (interval in self.professors_programs[prof][day]):
            return False
        
        # 3. Un profesor poate ține ore în maxim 7 intervale pe săptămână
        if prof in self.professors_programs:
            c = 0

            for zi in self.professors_programs[prof]:
                c += len(self.professors_programs[prof][zi])

            if c == 7:  # profesor cu program full
                return False
            
        # 4. O sală permite într-un interval orar prezența unui număr de studenți mai mic sau egal decât capacitatea sa maximă specificată - verificat implicit
        # 5. Toți studenții de la o materie trebuie să aibă alocate ore la acea materie - verific daca raman elevi nerepartizati dupa fiecare mutare
        # 6. Toți profesorii predau doar materiile pentru care sunt specializați - verific cand incerc sa mut
        # 7. În toate sălile se țin ore doar la materiile pentru care este repartizată sala - verific cand incerc sa mut
    
        return True


    def check_soft_constraints(self, day, interval, prof) -> int:
        '''
        Verifica daca o repartizare profesor - zi, interval este valida dpdv soft constraints.
        Returneaza numarul de constrangeri incalcate
        '''
        c = 0
        prof_info = self.professors[prof]

        if ('!' + day) in prof_info['Constrangeri']:
            c += 1

        for pref in prof_info['Constrangeri']:
            if pref.startswith('!') and '-' in pref:
                pref_start, pref_end = map(int, pref[1:].split('-'))
                if interval[0] >= pref_start and interval[1] <= pref_end:
                    c += 1
                    break
        return c


    def count_soft_constraints(self):
        '''
        Calculeaza numarul de soft constr incalcate in starea curenta.
        '''
        constr = 0

        for prof in self.professors_programs:
            prof_sch = self.professors_programs[prof]
            prof_pref = self.professors[prof]['Constrangeri']

            for day, intervals in prof_sch.items():
                if ('!' + day) in prof_pref:
                    constr += len(prof_sch[day])

                for interval in intervals:
                    if self.check_interval(interval, prof) == False:
                        constr += 1
                
        return constr

    def check_interval(self, interval, prof) -> bool:
        '''
        Verifica daca intervalul curent in care se tine o ora incalca o constrangere soft a profesorului
        '''
        prof_pref = self.professors[prof]['Constrangeri']

        for pref in prof_pref:
            if pref.startswith('!') and '-' in pref:
                interval_start, interval_end = map(int, pref[1:].split('-'))
                if interval[0] >= interval_start and interval[1] <= interval_end:
                    return False

        return True


    def generate_timetable(self) -> dict:
        '''
        Genereaza o stare initiala cu toate constrangerile hard respectate.
        Starea este optimizata pe cat posibil dpdv constrangeri soft (am favorizat mutari care sa reduca incalcarea constr soft).
        Asigurarea acoperirii este realizata prioritizand salile mari, materiile cu cei mai putini studenti nerepartizati si profesorii cu cele mai putine materii.
        Daca am materii neacoperite, repartizez fara sa tin cont de constrangerile soft.
        '''
        timetable = {}

        # prioritizez salile mai mari
        sorted_classrooms = sorted(self.classrooms.items(), key=lambda x: x[1]['Capacitate'], reverse=True)

        # prioritizez profesorii care au cele mai putine materii de predat
        sorted_professors = sorted(self.professors.items(), key=lambda x: len(x[1]['Materii']), reverse=False)

        for day in self.days:
            timetable[day] = {}

            for interval in self.intervals:
                if not isinstance(interval, tuple):
                    interval = ast.literal_eval(interval)

                timetable[day][interval] = {}

                # initializez
                for room, _ in self.classrooms.items():
                    timetable[day][interval][room] = []
          
                # prioritizez materiile cu cei mai putini studenti nerepartizati
                sorted_subjects = sorted(self.subjects_noofstudents.items(), key=lambda x: x[1], reverse=False)
                
                # incerc sa acopar o materie
                for subject, noofstud in sorted_subjects:
                    if noofstud > 0:  # am studenti nerepartizati la aceasta materie
                        for room, room_info in sorted_classrooms:
                            if self.subjects_noofstudents[subject] <= 0:  # opresc cautarea daca am toti studentii repartizati
                                break
                            # verific daca sala este disponibila
                            if subject in room_info['Materii'] and not timetable[day][interval][room]:
                                for prof, prof_info in sorted_professors:
                                    # verific daca profesorul poate sa predea aceasta ora dpdv constrangeri hard
                                    if subject in prof_info['Materii'] and self.check_hard_constraints(day, interval, room, subject, prof):
                                        # prioritizez intervale pe care le profesorul le prefera pentru optimizare solutie initiala
                                        ok = self.check_interval(interval, prof)
                                        if not ok:  # punerea orei aici ar incalca constrangere de interval
                                            continue

                                        timetable[day][interval][room] = (prof, subject)

                                        self.subjects_noofstudents[subject] -= room_info['Capacitate']

                                        if prof in self.professors_programs:
                                            if day in self.professors_programs[prof]:
                                                self.professors_programs[prof][day].append(interval)
                                            else:
                                                self.professors_programs[prof][day] = [interval]
                                        else:
                                            self.professors_programs[prof] = {day:[interval]}
                                        break

                                    else:
                                        continue

        # verific daca au ramas studenti nerepartizati in urma prioritizarii preferintelor soft ale profesorului
        # trebuie neaparat sa repartizez materia indiferent de constrangerile soft pe care le incalca, pentru a nu ramane materii neacoperite
        for materie, nostud in self.subjects_noofstudents.items():
            if nostud > 0:
                for ziua in self.days:
                    if self.subjects_noofstudents[materie] <= 0:
                        break
                    for interval in self.intervals:
                        if self.subjects_noofstudents[materie] <= 0:
                            break
                        if not isinstance(interval, tuple):
                            interval = ast.literal_eval(interval)
                        for sala, sala_info in self.classrooms.items():
                            if self.subjects_noofstudents[materie] <= 0:
                                break
                            for prof, prof_info in self.professors.items():
                                if (not timetable[ziua][interval][sala]) and (materie in prof_info['Materii']) and (self.check_hard_constraints(ziua, interval, sala, materie, prof)):
                                    # adaug in orar
                                    timetable[ziua][interval][sala] = (prof, materie)

                                    # adaug in programul profesorului
                                    if prof in self.professors_programs:
                                        if ziua in self.professors_programs[prof]:
                                            self.professors_programs[prof][ziua].append(interval)
                                        else:
                                            self.professors_programs[prof][ziua] = [interval]
                                    else:
                                        self.professors_programs[prof] = {ziua:[interval]}

                                    # actualizez numarul de studenti nerepartizatis
                                    self.subjects_noofstudents[materie] -= sala_info['Capacitate']

                                    if self.subjects_noofstudents[materie] <= 0:
                                        break
                                else:
                                    continue

        return timetable


    def apply_move(self, day_from, interval_from, room_from, professor_from, day_to, interval_to, room_to, professor_to, subject, move, subject2 = None):
        '''
        Construiește o nouă stare în care mutăm activitatea (materia) dintr-un interval/sală în altul.

        Întoarce o nouă instanță TimetableState care reprezintă starea orarului după mutare.

        Tot aici verific si daca mutarea este valida dpdv hard constraints
        
        Move e 1 pentru mutare si 2 pentru permutare
        '''

        new_timetable = deepcopy(self)  # pentru a evita modificările în obiectul curent
        if not isinstance(interval_to, tuple):
            interval_to = ast.literal_eval(interval_to)

        if not isinstance(interval_from, tuple):
            interval_from = ast.literal_eval(interval_from)

        # mut ora dintr-un interval in altul care e gol
        if move == 1:
            # verific daca raman elevi nerepartizati in urma mutarii
            old_room_capacity = new_timetable.classrooms[room_from]['Capacitate']
            new_room_capacity = new_timetable.classrooms[room_to]['Capacitate']
            if subject in new_timetable.subjects_noofstudents:
                not_rep = new_timetable.subjects_noofstudents[subject] + old_room_capacity - new_room_capacity
                if not_rep > 0:
                    return None

            # verific daca profesorul la care vreau sa mut e ocupat
            if (professor_to in new_timetable.professors_programs) and (day_to in new_timetable.professors_programs[professor_to]) and (interval_to in new_timetable.professors_programs[professor_to][day_to]) and move == 1:
                return None
            
            # verific daca profesorul la care vreau sa mut poate prelua ora sau are programul full
            if professor_to != professor_from and professor_to in self.professors_programs:
                c = 0
                for zi in self.professors_programs[professor_to]:
                    c += len(self.professors_programs[professor_to][zi])
                if c >= 7 and move == 1:
                    return None

            # pun ora pe care vreau sa o mut in orar la noua pozitie
            new_timetable.timetable[day_to][interval_to][room_to] = (professor_to, subject)

            # golesc sala in intervalul acela
            new_timetable.timetable[day_from][interval_from][room_from] = []
            
            # actualizez programul profesorului
            new_timetable.professors_programs[professor_from][day_from].remove(interval_from)

            if professor_to not in new_timetable.professors_programs:
                new_timetable.professors_programs[professor_to] = {day_to : [interval_to]}
            else:
                if day_to in new_timetable.professors_programs[professor_to]:
                    new_timetable.professors_programs[professor_to][day_to].append(interval_to)
                else:
                    new_timetable.professors_programs[professor_to][day_to] = [interval_to]

            # actualizez repartizarea elevilor
            old_room_capacity = new_timetable.classrooms[room_from]['Capacitate']
            new_room_capacity = new_timetable.classrooms[room_to]['Capacitate']

            new_timetable.subjects_noofstudents[subject] += old_room_capacity  # adaug la studentii nerepartizarti cati erau in vechea sala
            new_timetable.subjects_noofstudents[subject] -= new_room_capacity  # scad din stundentii nerepartizati cati intra in noua sala
        
        elif move == 2:
            # verific daca profesorii predau (in alte sali) in intervalele in care vreau sa ii pun
            if (day_to in new_timetable.professors_programs[professor_from]) and (interval_to in new_timetable.professors_programs[professor_from][day_to]):
                return None
            
            if (day_from in new_timetable.professors_programs[professor_to]) and (interval_from in new_timetable.professors_programs[professor_to][day_from]):
                return None
        
            if professor_to == professor_from:
                return None
            
            if room_to != room_from:
                return None
            
            # actualizez orarul
            new_timetable.timetable[day_to][interval_to][room_to] = (professor_from, subject)
            new_timetable.timetable[day_from][interval_from][room_from] = (professor_to, subject2)

            # actualizez programul profesorilor
            new_timetable.professors_programs[professor_from][day_from].remove(interval_from)
            if day_to not in new_timetable.professors_programs[professor_from]:
                new_timetable.professors_programs[professor_from][day_to] = [interval_to]
            else:
                new_timetable.professors_programs[professor_from][day_to].append(interval_to)

            new_timetable.professors_programs[professor_to][day_to].remove(interval_to)

            if day_from in new_timetable.professors_programs[professor_to]:
                new_timetable.professors_programs[professor_to][day_from].append(interval_from)
            else:
                new_timetable.professors_programs[professor_to][day_from] = [interval_from]

        return new_timetable

    def get_next_states(self) -> list["TimetableState"]:
        next_states = []

        # mut orele care genereaza cel putin o incalcare a constrangerilor soft
        for ziua, intervale in self.timetable.items():  # zi : dictionar intervale
            for interval, sali in intervale.items():    # interval : dictionar sali
                for sala, activitate in sali.items():   # sala : (tuplu prof, materie)
                    if activitate:   # exista o ora in acel interval in acea sala
                        profesor = activitate[0]
                        materie = activitate[1]

                        if self.check_soft_constraints(ziua, interval, profesor) == 0:  # ora curenta nu incalca nicio constrangere soft, deci nu vreau sa o mut
                            continue

                        for new_ziua, new_intervale in self.timetable.items():
                            for new_interval, _ in new_intervale.items():
                                sorted_classrooms = sorted(self.classrooms.items(), key=lambda x: x[1]['Capacitate'], reverse=True)
                                for new_sala, _ in sorted_classrooms:
                                    if (materie not in self.classrooms[new_sala]['Materii']):
                                        continue
                                    # daca exista deja o ora in intervalul acesta, incerc sa permut avand in vedere constrangerile celor 2 profesori
                                    if self.timetable[new_ziua][new_interval][new_sala]:
                                        if sala == new_sala and not(ziua == new_ziua and interval == new_interval):
                                            activitate_deja_programata = self.timetable[new_ziua][new_interval][new_sala]
                                            profesor_deja = activitate_deja_programata[0]
                                            materie_deja = activitate_deja_programata[1]
                                            if profesor_deja == profesor:
                                                continue

                                            if self.check_soft_constraints(new_ziua, new_interval, profesor_deja) == 0:  # ora existenta nu incalca constrangeri => nu ma intereseaza sa o mut
                                                continue

                                            # permut doar daca ora existenta incalca si ea constrangeri
                                            if self.check_soft_constraints(new_ziua, new_interval, profesor_deja):
                                                new_state = self.apply_move(ziua, interval, sala, profesor, new_ziua, new_interval, new_sala, profesor_deja, materie, 2, materie_deja)
                                                if new_state is not None:  # mutarea se poate realiza, adica nu incalca constrangeri hard
                                                        next_states.append(new_state)

                                    # daca nu exista deja o ora in interval, incerc sa mut avand in vedere constrangerile profesorului nou
                                    else:
                                        for new_prof, new_prof_info in self.professors.items():
                                            if (materie not in new_prof_info['Materii']):
                                                continue

                                            # verific daca mutarea materiei va genera constrangeri
                                            if self.check_soft_constraints(new_ziua, new_interval, new_prof) == 0:
                                                new_state = self.apply_move(ziua, interval, sala, profesor, new_ziua, new_interval, new_sala, new_prof, materie, 1)
                                                if new_state is not None:  # miscarera se poate realiza, adica nu incalca constrangeri hard
                                                    next_states.append(new_state)

        return next_states


def hill_climbing(initial: TimetableState, max_iters: int = 100) -> TimetableState:
        iters, states = 0, 0
        state = deepcopy(initial)

        while iters < max_iters:
            iters += 1
            curr_conflicts = state.count_soft_constraints()  # retin numarul de conflicte din current state
            print("iteration ",  iters)

            # daca e zero => am gasit o solutie
            if curr_conflicts == 0:
                break

            # STOCHASTIC HILL CLIMBING
            better_neigh = []  # lista de vecini "mai buni"

            print("computing neighbours... ")
            neighbours = state.get_next_states()
            print("found ", len(neighbours), " neighbours")

            for neigh in neighbours:
                states += 1
                neigh_conflicts = neigh.count_soft_constraints()
                if neigh_conflicts <= curr_conflicts:  # conflictele egale inseamna ca am mutat o ora dintr o zi pe care profesorul NU o prefera, dar inca are ore in acea
                    better_neigh.append(neigh)

            state = random.choice(better_neigh)
            print("current conflicts:", state.count_soft_constraints())

        print("------------------------------------------------- RESULT HC =", state.count_soft_constraints(), "-------------------------------------------------")
        print("iterations:", iters, "\nnumber of states: ", states)
        return state


def parse_arguments():
    parser = argparse.ArgumentParser(description="Programul va primi ca argumente algoritmul (csp sau hc) și fisierul de intrare.")
    parser.add_argument("algorithm", choices=["csp", "hc"], help="Algoritmul: csp sau hc")
    parser.add_argument("input_file", type=str, help="Nume fisier de intrare")

    args = parser.parse_args()
    return args.algorithm, args.input_file


def read_input_file(input_file_path: str) -> dict:
    return utils.read_yaml_file(input_file_path)


if __name__ == "__main__":
    # citire din fisier & generare orar initial
    algorithm, input_file = parse_arguments()
    input_file_path = './inputs/' + input_file

    data = read_input_file(input_file_path)
    initial_state = TimetableState(data)

    print("-------------------------------------------------- INITIAL TIMETABLE --------------------------------------------------")
    print("Initial conflicts: ",  initial_state.count_soft_constraints())

    print("-------------------------------------------------------- HC --------------------------------------------------------")
    output_state = hill_climbing(initial_state)

    # scriere in fisier
    output_file_path = './outputs/' + input_file.split('.')[0] + '.txt'
    with open(output_file_path, 'w') as fisier:
        fisier.write(utils.pretty_print_timetable(output_state.timetable, input_file_path))
    
    # scrie pe ecran
    print(utils.pretty_print_timetable(output_state.timetable, input_file_path))
    print("---------------------------------------------------------------------------------------------------------------------")
