import os

class Nurse:
    def __init__(self, name, contract, level, zzper, headnurse, resuscitate):
        self.name = name
        self.contract = contract
        self.level = level
        self.zzper = zzper
        self.headnurse = headnurse
        self.resuscitate = resuscitate

    def __str__(self):
        return f"{self.name} {self.contract} {self.level} {self.zzper} {self.headnurse} {self.resuscitate}"

class Nurses:
    def __init__(self, fn):
        self.fn = fn
        self.nurses = self._InitFromFile(self.fn)
        pass

    def __str__(self):
        for nurse in self.nurses:
            print(nurse)
        return ""

    def _InitFromFile(self, fn):
        assert(fn)
        assert(os.path.isfile(fn))

        nurses = []
        with open(fn) as f:
            while(True):
                line = f.readline()
                
                if not line:
                    break

                if line.startswith("#"): # comment
                    continue
                
                line_parts = line.split(";")
                name        = line_parts[0]
                contract    = float(line_parts[1])
                level       = int(line_parts[2])
                zzper       = bool(line_parts[3])
                headnurse   = bool(line_parts[4])
                resuscitate = bool(line_parts[5])

                nurses.append(Nurse(name, contract, level, zzper, headnurse, resuscitate))
        return nurses
